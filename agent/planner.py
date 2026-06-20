"""Planner: turn a natural-language question into a structured plan + INTENT.

The plan now carries an `intent` so the agent answers different *kinds* of
question (not just "wait N years"), and declines questions the city-level data
cannot truthfully answer.

Supported intents (everything the engine can actually compute):
  cost_of_waiting   — extra cost of waiting N years            (default)
  break_even        — how long can we wait before it stops paying off
  savings_now       — how much acting now saves vs doing nothing
  outcome_at_horizon— how many people are homeless at the horizon
  compare_budgets   — compare two or more annual budgets
  compare_mix       — compare prevention / rapid-rehousing / supportive-housing mixes
  sensitivity       — which assumption matters most / are we least sure about
  greeting          — small-talk / "what can you do?" -> friendly orientation (no engine)
  out_of_scope      — anything individual-level or sub-CoC -> decline politely

Two planners, same output shape:
  rule_based  — deterministic; the always-works fallback + the can't-fail demo mode.
  claude      — Claude Sonnet 4.6 via the Anthropic API (frontier reasoning + prose).

WAITCOST_PLANNER selects the mode (default **auto**):
  auto   — Claude-first; if no API key is set or the call errors, fall back to rules
           silently (the default — judges see the LLM is live, the demo never breaks).
  claude — force Claude; raise if the API is unreachable (use to prove the LLM path).
  rule   — pure deterministic; never touches the network (the air-gapped, reproducible
           demo, and the guaranteed offline take).
"""
import json
import os
import re

from agent import capabilities as caps
from agent import llm

# Derived from the capability registry (agent/capabilities) so it can never drift
# from the routing / prompt / chart bindings. Membership is what callers rely on.
INTENTS = caps.intents_tuple()

# Domain vocabulary — if a question contains NONE of these (and isn't a greeting
# or out-of-scope), the rule planner routes it to `clarify` (guide the user) rather
# than silently defaulting to cost_of_waiting. Kept broad so real questions pass.
_DOMAIN_RE = re.compile(
    r"\b(wait|delay|cost|spend|spending|save|saving|savings|budget|million|\$|invest|"
    r"roi|return|benefit|worth|payback|pay off|homeless|shelter|unsheltered|chronic|"
    r"housing|house|prevention|rapid|supportive|psh|equit|race|racial|disparit|"
    r"break.?even|how (long|many)|people|person|per.?capita|outcome|horizon|year|"
    r"city|cities|region|context|profile|situation|sensitiv|assumption|uncertain|"
    r"confiden|driver|program|intervention|act now|do nothing|status quo)\b", re.I)


def _mode():
    # Default is now `auto`: Claude-first with an automatic, invisible rule fallback.
    return os.environ.get("WAITCOST_PLANNER", "auto").lower()


def plan(question, params):
    mode = _mode()
    if mode == "rule":
        result = _rule_based_plan(question, params)
    elif mode == "claude":
        # Forced Claude: let errors propagate (proves the LLM path is really live).
        result = _claude_plan(question, params)
    else:
        # auto (default): use Claude when a key is present, else fall back silently
        # to the deterministic rule planner — never stall, never crash.
        result = None
        if llm.claude_available():
            try:
                result = _claude_plan(question, params)
            except Exception:
                result = None
        if result is None:
            result = _rule_based_plan(question, params)
    # Two routers: attach the deterministic classifier's read alongside the LLM's,
    # so the confidence gate can ask instead of guess when they disagree.
    result["rule_intent"] = classify_intent(question)
    result = _apply_safety_rail(question, result)        # safety first — hard veto
    result = _apply_confidence_gate(result)              # then: ask-don't-guess
    return _normalize_calls(question, result)


# --- confidence gate: ask, don't guess (runs AFTER the safety rail) ----------
_ROUTE_CONF_THRESH = 0.6
_SAFE_INTENTS = {"out_of_scope"}


def _apply_confidence_gate(result):
    """When the LLM and rule routers disagree on a NON-safety intent at low
    confidence, route to `clarify` and surface both readings — instead of silently
    committing to one. Safety always wins (the rail ran first and is never softened);
    rule mode (no Claude confidence) skips the gate."""
    if result.get("safety_override"):
        return result
    conf = result.get("route_confidence")
    claude_intent = result.get("claude_intent")
    if conf is None or claude_intent is None:        # rule mode / no LLM route
        return result
    final = result.get("intent")
    rule_intent = result.get("rule_intent")
    if final in _SAFE_INTENTS or rule_intent in _SAFE_INTENTS:
        return result
    disagree = rule_intent is not None and rule_intent != final
    if disagree and conf < _ROUTE_CONF_THRESH:
        seen, alts = set(), []
        for it in (final, rule_intent, result.get("second_choice")):
            if it and it not in seen and it not in _SAFE_INTENTS:
                seen.add(it)
                cap = caps.by_intent(it)
                alts.append({"intent": it, "label": (cap.summary if cap else it)})
        result["intent"] = "clarify"
        result["route_alternatives"] = alts
    return result


# --- deterministic safety rail (authoritative over ANY planner, incl. the LLM) --
def _rule_says_out_of_scope(q):
    """True iff the deterministic classifier — which respects the cost_per_person-
    before-out_of_scope priority so an AGGREGATE 'cost per person' is NOT read as
    profiling — decides this is an individual / sub-CoC question."""
    return caps.classify(q or "") == "out_of_scope"


def _apply_safety_rail(question, result):
    """The 'never profile individuals or sub-CoC geographies' promise must not
    depend on the language model. If the deterministic rule flags the question as
    out-of-scope, we force out_of_scope no matter what the planner (especially
    Claude) chose. This is the layered router: an LLM proposes, a rule vetoes."""
    if result.get("intent") != "out_of_scope" and _rule_says_out_of_scope(question):
        result["intent"] = "out_of_scope"
        result["safety_override"] = True
    return result


# --- shared parameter extraction -------------------------------------------
def _extract_delay(q):
    m = re.search(r"(?:wait|delay|in|after|for)\D{0,12}(\d+)\s*year", q)
    return int(m.group(1)) if m else 5


# Annual budgets are tracked in $M. Understand the common units so "$5B" and
# "$500k" aren't silently dropped (which would fall back to default budgets).
_BUDGET_UNIT = {"m": 1.0, "million": 1.0, "mm": 1.0,
                "b": 1000.0, "billion": 1000.0, "bn": 1000.0,
                "k": 0.001, "thousand": 0.001}
_BUDGET_RE_UNIT = re.compile(
    r"\$?\s*(\d+(?:\.\d+)?)\s*(million|billion|thousand|mm|bn|m|b|k)\b", re.I)


def _extract_budgets(q):
    """Annual budgets found in the text, normalized to $M (m/million=1, b/billion=×1000, k=÷1000)."""
    return [round(float(n) * _BUDGET_UNIT[u.lower()], 6) for n, u in _BUDGET_RE_UNIT.findall(q)]


def _distinct_budgets(q):
    """All distinct dollar amounts, order-preserving (dedupes '$15M and $15M')."""
    seen, out = set(), []
    for b in _extract_budgets(q):
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def _extract_delays(q):
    """All distinct delay-year values mentioned (e.g. 'wait 1, 3, or 5 years')."""
    seen, out = [], []
    for x in re.findall(r"(\d+)\s*year", q):
        v = int(x)
        if v not in seen:
            seen.append(v)
            out.append(v)
    return out


# --- completeness normalizer: one question -> a LIST of typed tool calls -----
# A deterministic post-plan layer (mirrors _apply_safety_rail: a planner proposes,
# a rule completes/vetoes). It re-reads the raw question for ALL parameters after
# classification — independent of whether Claude or the rules planned — and ensures
# every parsed value is COVERED by a call (no silent drop). Cardinality is N calls,
# not list-valued args, so the executor stays uniform: "wait 3y on $1M and $15M"
# becomes two `cost_of_waiting` calls.
SINGLE_BUDGET_ENGINE_INTENTS = frozenset({
    "cost_of_waiting", "roi", "savings_now", "break_even",
    "cost_per_person", "outcome_at_horizon",
})
MAX_CALLS = 6
_BUDGET_MAX_MUSD = 1e4   # clamp absurd inputs; budget must be > 0 and <= this
_COMPARE_CUE = re.compile(r"\b(better|best|which|versus|vs\.?|compare|cheaper|lowest)\b", re.I)
_WAITING_CUE = re.compile(r"\b(wait|delay|cost of waiting|cost to wait|hold off|postpone)\b", re.I)


def _call_from_plan(result):
    """The single call that reproduces today's flat plan (back-compat)."""
    args = {}
    if result.get("budget_musd") is not None:
        args["budget_musd"] = result["budget_musd"]
    if result.get("delay_years") is not None:
        args["delay_years"] = result["delay_years"]
    if result.get("budgets"):
        args["budgets"] = result["budgets"]
    if result.get("mix"):
        args["mix"] = result["mix"]
    return {"tool": result.get("intent"), "args": args}


def _normalize_calls(question, result):
    q = (question or "").lower()
    intent = result.get("intent")
    budgets = _distinct_budgets(q)
    delays = _extract_delays(q)
    result["parsed_params"] = {"budgets": budgets, "delays": delays}
    notes = []

    # No-default-without-saying-so: if the intent consumes a budget/delay and the
    # user named none, the value is a default — flag it so the answer can say so
    # (never silently answer an unasked question). Non-engine intents have no
    # params, so this stays empty for them.
    cap = caps.by_intent(intent)
    cap_params = set(cap.params) if cap else set()
    defaults = []
    if ("budget_musd" in cap_params or "budgets" in cap_params) and not budgets:
        defaults.append("a budget")
    if "delay_years" in cap_params and not delays:
        defaults.append("a delay")
    result["defaults_used"] = defaults

    # Non-engine / safety intents are never swept or expanded — one call, as planned.
    if intent in ("out_of_scope", "greeting", "clarify") or len(budgets) < 2:
        result["calls"] = [_call_from_plan(result)]
        result["coverage_notes"] = notes
        return result

    # Validate the parsed budgets: drop non-positive / absurd values explicitly.
    valid = [b for b in budgets if 0 < b <= _BUDGET_MAX_MUSD]
    dropped = [b for b in budgets if b not in valid]
    if dropped:
        notes.append("Ignored invalid budget value(s): "
                     + ", ".join(f"${b:g}M" for b in dropped) + ".")

    compare_cue = bool(_COMPARE_CUE.search(q))
    waiting_cue = bool(_WAITING_CUE.search(q))

    # The user's chosen default for "$A and $B": answer the cost of waiting for EACH
    # budget. A waiting/delay framing reinterprets a rule-routed `compare_budgets`
    # (the 2-budget trigger) as a cost_of_waiting sweep, so rule and Claude modes agree
    # — and it wins even over a "compare" cue, because "compare the cost of waiting at
    # $A and $B" wants the figure for each, not the lowest-total-cost budget.
    if len(valid) >= 2 and waiting_cue:
        intent = "cost_of_waiting"
        result["intent"] = "cost_of_waiting"
        expand = True
    elif intent in SINGLE_BUDGET_ENGINE_INTENTS and len(valid) >= 2 and not compare_cue:
        expand = True
    else:
        expand = False   # compare_budgets / compare_mix keep their list-arg handlers

    if expand:
        if len(valid) > MAX_CALLS:
            notes.append(f"Showing the first {MAX_CALLS} of {len(valid)} budgets (cap).")
            valid = valid[:MAX_CALLS]
        delay = result.get("delay_years", 5)
        result["calls"] = [
            {"tool": intent, "args": {"budget_musd": b, "delay_years": delay}}
            for b in valid
        ]
        result["budget_musd"] = valid[0]                       # legacy mirror = first call
        result["budgets"] = valid if len(valid) >= 2 else None
    else:
        result["calls"] = [_call_from_plan(result)]

    result["coverage_notes"] = notes
    return result


# --- intent classification (rule-based) ------------------------------------
def classify_intent(q):
    """Walk the capability registry in priority order (its triggers are the
    per-intent regexes that used to live here inline). The final scope gate is
    kept here: an in-scope-but-unmapped question -> cost_of_waiting (the
    default); a question with no engine vocabulary at all -> clarify."""
    q = (q or "").lower()
    hit = caps.classify(q)
    if hit is not None:
        return hit
    return "cost_of_waiting" if _DOMAIN_RE.search(q) else "clarify"


def _rule_based_plan(question, params):
    q = (question or "").lower()
    default_budget = float(params["meta"].get("default_budget_musd", 10.0))
    budgets = _extract_budgets(q)
    intent = classify_intent(q)
    return {
        "question": question,
        "intent": intent,
        "delay_years": _extract_delay(q),
        "budget_musd": budgets[0] if budgets else default_budget,
        "budgets": budgets if len(budgets) >= 2 else None,
        "mix": None,
        "scenarios": ["status_quo", "act_now", "delay"],
        "planner": "rule_based_fallback",
    }


# --- Claude planner (Anthropic API) ----------------------------------------
# The system prompt is GENERATED from the capability registry: each capability
# supplies its own `when_to_use` (the intent meaning) and an optional
# `plan_example` (the few-shot). Adding a capability auto-updates this prompt —
# no hand-editing here. One registry, three consumers (rule regex, this Claude
# prompt, the Phase-2 tool schemas) — they can never drift. This is the
# progressive-disclosure win.
_PLAN_SYS_TEMPLATE = (
    "You convert a policymaker's question about a homelessness cost-of-inaction "
    "simulator into a JSON plan. Respond with ONLY JSON: "
    '{"intent": <one of %(intents)s>, "delay_years": <int>, '
    '"budget_musd": <number>, "budgets": <array of numbers or null>, '
    '"route_confidence": <0..1 how sure you are of the intent>, '
    '"second_choice": <the next most likely intent, or null>}.\n'
    "intent meanings:\n%(meanings)s\n"
    "delay_years default 5 if unstated; budget_musd default %(default)s if unstated. "
    "Set route_confidence below 0.6 when the question is genuinely ambiguous between "
    "two intents, and name that other intent as second_choice.\n"
    "Examples:\n%(examples)s"
)


def build_plan_system(default):
    """Assemble the planner system prompt from the registry (progressive
    disclosure: short menu of intents + their meanings + examples)."""
    return _PLAN_SYS_TEMPLATE % {
        "intents": list(caps.intents_tuple()),
        "meanings": caps.plan_meanings(),
        "examples": caps.plan_examples(default),
        "default": default,
    }


def _claude_plan(question, params):
    default_budget = float(params["meta"].get("default_budget_musd", 10.0))
    system = build_plan_system(default_budget)
    text = llm.generate(system, f'Q: "{question}"\nJSON:',
                        want_json=True, temperature=0.0, max_tokens=256)
    if not text:
        # No key / API error: raise so forced `claude` mode fails loudly and `auto`
        # mode's try/except falls back to the rule planner.
        raise RuntimeError("Claude planner returned no output")
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    raw_intent = data.get("intent", "cost_of_waiting")
    intent = raw_intent
    if intent not in INTENTS:
        # Claude returned an unknown label — don't blindly assume a cost analysis.
        # Defer to the deterministic rule classifier (which routes off-topic to
        # `clarify` and in-scope-unmapped to `cost_of_waiting`). LLM proposes,
        # rules disambiguate — the two routers are complementary.
        intent = classify_intent(question)
    budgets = data.get("budgets")
    second = data.get("second_choice")
    try:
        conf = float(data.get("route_confidence", 1.0))
    except (TypeError, ValueError):
        conf = 1.0
    return {
        "question": question,
        "intent": intent,
        "delay_years": int(data.get("delay_years", 5)),
        "budget_musd": float(data.get("budget_musd", default_budget)),
        "budgets": [float(b) for b in budgets] if isinstance(budgets, list) and len(budgets) >= 2 else None,
        "mix": None,
        "scenarios": ["status_quo", "act_now", "delay"],
        "planner": "claude",
        # Confidence-gating signals (used by _apply_confidence_gate). claude_intent
        # is the model's own pick, preserved even if we deferred to the rules above.
        "claude_intent": intent,
        "route_confidence": max(0.0, min(1.0, conf)),
        "second_choice": second if second in INTENTS else None,
    }


# --- number-guard for any LLM-authored prose -------------------------------
# Match money ($12, $12.3M, 1,234) and bare numbers so we can verify the LLM
# only ever repeats figures we computed and handed it.
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers_in(text):
    """The set of numeric tokens in `text`, normalized (commas stripped, trailing
    zeros/decimal point removed) so '1,234' == '1234' and '12.0' == '12'."""
    out = set()
    for tok in _NUM_RE.findall(text or ""):
        norm = tok.replace(",", "")
        if "." in norm:
            norm = norm.rstrip("0").rstrip(".")
        if norm:
            out.add(norm)
    return out


def numbers_are_grounded(text, allowed_text):
    """True iff every number in `text` also appears in `allowed_text` (the facts
    we passed the model). This is the guard that stops the LLM inventing figures:
    on any unseen number we reject the LLM prose and use the deterministic brief.
    A more fluent writer makes this guard matter more, not less.
    """
    allowed = _numbers_in(allowed_text)
    # Tolerate years and the small integers (0-31) the model uses for prose
    # ("over 10 years", "first") — those aren't headline figures.
    allowed |= {str(n) for n in range(0, 32)}
    allowed |= {"2023", "2024", "2025"}
    return _numbers_in(text).issubset(allowed)


# Steers the model toward an analyst's voice while the number-guard enforces that
# every figure it writes was one we handed it.
_NARRATOR_SYS = ("You are a careful city budget analyst. Use ONLY the figures you "
                 "are given; never invent, round, or compute a new number.")


def narrate_brief(facts):
    """Feature ③ — let Claude WRITE the one-page memo from the engine's computed
    `facts` (a dict of strings/numbers). Returns the memo markdown, or None on
    mode==rule / no key / API error / a failed number guard.

    The caller treats None as "use the deterministic write_brief markdown".
    """
    if _mode() == "rule":
        return None
    # Render the facts as a compact, unambiguous block; this is also the
    # whitelist of numbers the model is allowed to echo.
    fact_lines = "\n".join(f"- {k}: {v}" for k, v in facts.items())
    prompt = (
        "Write a SHORT one-page decision memo (<=200 words, markdown, with a "
        "'## Decision memo' heading) for a city budget director, using ONLY the "
        "figures provided below. Every dollar figure and statistic in your memo "
        "must appear verbatim in the FACTS. State the headline cost of waiting and "
        "its range, name the top driver, mention the backtest error as a "
        "credibility note, and end with the disclaimer that the tool informs (does "
        "not decide) the timing.\n\nFACTS:\n" + fact_lines
    )
    text = llm.generate(_NARRATOR_SYS, prompt, temperature=0.2, max_tokens=320)
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    # The critical guard: reject if the model emitted any number we didn't give it.
    if not numbers_are_grounded(text, fact_lines):
        return None
    return text


def narrate_grounded(prompt, allowed_facts_text):
    """Generic number-guarded narration: run Claude on `prompt`, but return the
    prose ONLY if every figure in it also appears in `allowed_facts_text`. Returns
    None on rule mode / no key / API error / empty / a failed number guard — the
    caller then uses its deterministic template.

    This is the same guard as `narrate_brief`, lifted out so the CityBriefAgent can
    let the model phrase a city's situation/plan without ever inventing a statistic.
    """
    if _mode() == "rule":
        return None
    text = llm.generate(_NARRATOR_SYS, prompt, temperature=0.2, max_tokens=320)
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    if not numbers_are_grounded(text, allowed_facts_text):
        return None
    return text


def explain_brief(brief_markdown, max_sentences=3):
    """Optional plain-English gloss from Claude. Returns None if not enabled."""
    if _mode() == "rule":
        return None
    prompt = (
        f"In at most {max_sentences} plain sentences, summarize the decision brief "
        "below for a city budget director. State the headline figure and that the "
        "tool informs (does not decide) the timing. Do not invent numbers.\n\n"
        + brief_markdown
    )
    text = llm.generate(_NARRATOR_SYS, prompt, temperature=0.2, max_tokens=200)
    return text.strip() if text else None
