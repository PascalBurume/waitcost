"""The Evaluator agent — the 5th agent: a post-answer critic.

It runs in the orchestrator AFTER the analyst produces an answer and BEFORE the
user sees it. The governing principle: the harm in a budget tool is not being
wrong — it's being *confidently* wrong and silent about it. So when something is
off, we surface *what* went wrong instead of a polished, plausible, wrong answer.

Hybrid by design: the hard guarantees are deterministic code (checks 1–5 here);
an LLM judge assesses only the one thing code can't — "does this answer THIS
question?" (check 6, added separately). The evaluator can flag / annotate /
repair / decline — it can NEVER change or invent an engine figure. It is
**annotate-first**: uncertainty becomes a *warn* (answer shown with a caveat),
not a block; refusal is reserved for true scope/data violations.
"""
import re

from agent import capabilities as caps
from agent import planner

# Intents that don't run the cost engine — nothing to ground, no scope-leak risk.
_NON_ENGINE = {"greeting", "clarify", "out_of_scope", "city_situation",
               "care_plan", "concept_qa", "data_lookup"}

# status precedence (worst first) when folding per-check results into a verdict
_DECLINE_ON = {"scope"}            # a real scope violation → decline
_REPAIR_ON = {"grounding", "chart_text", "question_match"}   # fixable by re-running


def _facts_text(facts):
    """Render the engine fact dict as the whitelist of numbers the prose may echo."""
    if not facts:
        return ""
    return "\n".join(f"- {k}: {v}" for k, v in facts.items())


_HEAD_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(B|M)\b", re.I)


def _headline_musd(text):
    """First dollar figure in the text, normalized to $M (so $5.0B → 5000)."""
    m = _HEAD_RE.search(text or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return v * 1000.0 if m.group(2).upper() == "B" else v


def evaluate(question, result, params, *, facts=None, llm_memo=None, question_match=None):
    """Return a ResponseCheck dict for an engine answer.

    `facts` is the engine fact dict (the grounding whitelist). `llm_memo`, when
    provided, is the RAW LLM-authored memo to ground — passed separately because the
    assembled brief prepends an engine-grounded verdict citation whose figures aren't
    in the compact fact set. `question_match`, when provided, is the LLM judge verdict
    {ok, reason} for check 6 — injected by the orchestrator so this module stays
    import-light and testable without a network call.
    """
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    intent = result.get("intent") or (result.get("plan") or {}).get("intent")

    # 1 — Grounding: an LLM-authored memo may only echo engine figures. We re-ground
    #     ONLY the raw LLM memo (`llm_memo`) — belt-and-suspenders on top of the
    #     narrate_brief guard. The deterministic brief is grounded by construction and
    #     its prose legitimately carries figures outside the compact fact set (discount
    #     %, MC runs, the verdict-citation prefix), so it is never re-grounded here.
    allowed = _facts_text(facts)
    if llm_memo and allowed:
        ok = planner.numbers_are_grounded(llm_memo, allowed)
        add("grounding", "ok" if ok else "fail",
            "Every figure in the memo traces to the engine." if ok
            else "The memo states a number the engine didn't produce.")
    else:
        add("grounding", "ok", "Figures are engine-authored (deterministic brief).")

    # 2 — Scope: re-run the deterministic rail. An individual / sub-CoC question
    #     must never have reached the engine.
    leaked = (caps.classify(question) == "out_of_scope"
              and intent not in _NON_ENGINE)
    add("scope", "fail" if leaked else "ok",
        "This reads as an individual or sub-CoC question, but the engine answered it."
        if leaked else "In scope — city-level only.")

    # 3 — Parameter fidelity: surface any default-used / dropped value.
    plan = result.get("plan") or {}
    defaults = plan.get("defaults_used") or []
    notes = plan.get("coverage_notes") or []
    if defaults:
        add("parameters", "warn",
            "You didn't specify " + ", ".join(defaults)
            + " — I used the default. Change it?")
    elif notes:
        add("parameters", "warn", " ".join(notes))
    else:
        add("parameters", "ok", "Read your numbers as given.")

    # 4 — Data confidence: calibrated (LA) vs illustrative (other cities).
    meta = params.get("meta", {})
    vintage = str(meta.get("data_vintage", ""))
    calibrated = "CA-600" in str(meta.get("coc", "")) and "pending" not in vintage
    if calibrated:
        add("data", "ok", "Los Angeles is fully calibrated (HUD PIT + ACS + SPM flows).")
    else:
        add("data", "warn",
            f"{meta.get('coc', 'This city')} is illustrative — real PIT + ACS inflow, but "
            "flow/cost rates use LA priors. Treat the range as wide.")

    # 5 — Chart–text consistency: the stated headline must match the engine's
    #     cost-of-waiting median (the same figure the recommended chart is built
    #     from). Cheap and engine-derived — no Monte-Carlo re-run.
    cow = (result.get("comparison") or {}).get("cost_of_waiting") or {}
    engine_med = cow.get("extra_cost_median")
    if intent == "cost_of_waiting" and engine_med is not None:
        stated = _headline_musd(result.get("direct_answer"))
        engine_musd = engine_med / 1e6
        tol = max(1.0, abs(engine_musd) * 0.02)
        if stated is not None and abs(stated - engine_musd) > tol:
            add("chart_text", "fail",
                f"The headline (${stated:,.0f}M) doesn't match the engine figure (${engine_musd:,.0f}M).")
        else:
            add("chart_text", "ok", "The chart and the text show the same figure.")
    else:
        add("chart_text", "ok", "The chart is built from the same engine output as the text.")

    # 6 — Question-match (LLM judge), injected by the orchestrator (optional).
    if question_match is not None:
        ok = bool(question_match.get("ok", True))
        add("question_match", "ok" if ok else "fail",
            "Answers the question asked." if ok
            else (question_match.get("reason") or "May not answer the question you asked."))

    # Fold into a verdict (worst wins): decline > repair > warn > pass.
    failed = {c["name"] for c in checks if c["status"] == "fail"}
    if failed & _DECLINE_ON:
        status = "decline"
    elif failed & _REPAIR_ON:
        status = "repair"
    elif any(c["status"] == "warn" for c in checks):
        status = "warn"
    else:
        status = "pass"
    confidence = {"pass": "high", "warn": "medium", "repair": "low", "decline": "low"}[status]

    what_went_wrong = [c["detail"] for c in checks if c["status"] != "ok"]
    repair_hint = None
    if status == "repair":
        bad = ", ".join(sorted(failed & _REPAIR_ON))
        repair_hint = (f"The previous answer failed checks: {bad}. Recompute strictly from engine "
                       "output and make sure the response answers the user's actual question.")
    suggested = None
    if status == "decline":
        suggested = ("Ask about the city as a whole — e.g. "
                     "\"what does waiting 3 years cost at $15M/yr?\"")

    return {
        "status": status,
        "confidence": confidence,
        "checks": checks,
        "what_went_wrong": what_went_wrong,
        "repair_hint": repair_hint,
        "suggested_reformulation": suggested,
    }
