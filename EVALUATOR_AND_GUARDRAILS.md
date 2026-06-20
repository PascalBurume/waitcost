# WaitCost — The Evaluator Agent & "Make Errors Loud"

An add-on to `SONNET_MIGRATION_PLAN.md`. Two goals:
1. **Accuracy** — fix the cases where a typed question gets routed/answered wrong.
2. **Responsible AI** — a real answer to "if our AI gets it wrong, what happens to the user,
   and what have we done about it?"

The governing principle: **the harm is not being wrong — it's being *confidently* wrong and
silent about it.** So we add a 5th agent whose only job is to catch a bad answer *before the
user sees it* and, when something is off, **show the user exactly what went wrong** instead of a
polished, plausible, wrong response. We make our errors loud.

---

## 1. The accuracy problem, named

Today the pipeline is: planner proposes intent + params → `_apply_safety_rail` (forces
`out_of_scope`) → `_normalize_calls` (parameter completion) → engine → brief. Real failure cases
we see when a user types freely:

- **Misroute** — the wrong analysis runs ("ROI of the city's plan" → `care_plan` instead of `roi`).
- **Param misparse** — wrong budget/delay → right analysis, wrong dollar magnitude.
- **Silent default** — no budget in the text → quietly uses the $10M default and answers anyway.
- **Scope leak** — a cleverly worded individual/sub-CoC question slips past the regex rail.
- **Invented number** — narration emits a figure the engine never produced.
- **False confidence** — an un-calibrated city's answer looks as solid as Los Angeles.
- **Wrongful refusal** — a legitimate question gets declined (over-caution is also a failure).

Two layers fix these: **(A)** stop guessing when unsure (confidence-gated routing), and **(B)**
check the finished answer and surface what's wrong (the Evaluator).

---

## 2. Confidence-gated routing — stop guessing, start asking

The cheapest accuracy win, and a great Responsible-AI story: **when the routers disagree or
confidence is low, ask instead of guess.**

- **Two routers must agree.** You already run a layered router (LLM proposes, rule vetoes for
  scope). Extend it: also run `classify_intent` (rule) alongside Claude. If they **disagree on a
  non-safety intent**, that's a low-confidence signal.
- **Claude returns a confidence.** The planner JSON gains `route_confidence` (0–1) and a
  `second_choice` intent. Low confidence + disagreement → route to `clarify` and show the user the
  two interpretations to pick from, rather than silently committing to one.
- **Parameter echo.** Always surface the parsed reading back to the user — "I read this as: *cost
  of waiting · 3 years · $15M · Los Angeles*." A misparse becomes visible and one-click fixable
  instead of buried in the math.
- **No-default-without-saying-so.** If a budget/delay came from a default (user gave none), that is
  always flagged, never silent.

This alone removes most "the outcome is wrong" cases, because the system's failure mode shifts
from *guess wrong* to *ask a clarifying question*.

---

## 3. The Evaluator agent (the 5th agent)

A post-answer critic that runs in the orchestrator after the analyst produces a result and
**before** it's returned. New file `agent/evaluator.py`, `evaluate(question, result, params) ->
ResponseCheck`. Streamed as the final trajectory step ("Checking the answer…"), exposed on the API
as `result["response_check"]`, rendered as a panel under every answer.

**Hybrid by design — deterministic checks first, LLM judge only for meaning.** This matters: we do
*not* just trust one LLM to grade another. The hard guarantees are code; the model judges only the
one thing code can't — "does this actually answer the question?"

| # | Check | How | Type | On failure |
|---|---|---|---|---|
| 1 | **Grounding** | every number in the brief ∈ engine facts (`numbers_are_grounded`) | deterministic | repair → deterministic brief |
| 2 | **Scope** | re-run the safety rail; engine must not have run on an `out_of_scope` question | deterministic | decline |
| 3 | **Parameter fidelity** | parsed params vs raw text; flag any default-used / dropped value | deterministic | warn (annotate) |
| 4 | **Data confidence** | `check_data_support` / calibration level for the CoC | deterministic | warn (label "illustrative") |
| 5 | **Chart–text consistency** | the recommended chart's figure == the text's figure | deterministic | repair |
| 6 | **Question match** | "does this response answer THIS question?" | LLM judge (Sonnet) | repair → re-route |

**Verdict schema:**

```
ResponseCheck {
  status: "pass" | "warn" | "repair" | "decline",
  confidence: "high" | "medium" | "low",
  checks: [ { name, status: ok|warn|fail, detail } ],
  what_went_wrong: [ plain-language strings ],   // user-facing
  repair_hint: string | null,                    // fed back to the planner on repair
  suggested_reformulation: string | null         // shown on decline
}
```

**The self-correction loop (bounded).** On `repair` (e.g. question-match = no, or grounding fail),
the orchestrator re-plans **once** with `repair_hint` appended ("you answered ROI; the user asked
for the city's plan — re-route"), re-runs, re-evaluates. Still failing → `decline` with a clear
reason. The cap (1 retry) bounds latency and cost. This is genuine agentic self-correction — and a
visible reasoning step for the 35% criterion.

**The evaluator is itself guarded.** It can flag, annotate, repair, or decline — it can **never**
change an engine figure or invent one. And it is **annotate-first**: uncertainty becomes a *warn*
(answer shown with a caveat), not a block. Refusal is reserved for true scope/data violations, so
we don't trade one failure (false answer) for another (false refusal, F8).

---

## 4. "What went wrong" — what the user sees

Every answer carries a **Response Check** panel (see the mockup `response_check_panel.png`). Three
states:

- **Pass (high confidence).** A compact green strip: "Grounded · In scope · Answers your question ·
  Data: high (LA, calibrated)." Reassures without nagging.
- **Warn (answer shown, with caveats).** Yellow rows naming each issue in plain language:
  *"You didn't name a budget — I assumed $10M (LA default). Change it?"* / *"Chicago is illustrative,
  not calibrated like LA — treat the range as wide."*
- **Decline (no confident answer).** Instead of a wrong answer, a clear card: *"This looks like it's
  about a specific person or address. I only work at the city level — that's a deliberate privacy
  limit."* plus a **suggested reformulation** the user can click.

That panel *is* the answer to the mentor's question, made visible: when the AI is unsure or wrong,
the user is told *what* and *why*, and given a path forward — not handed a confident mistake.

---

## 5. Responsible-AI failure-mode register (the strong answer)

For each failure: **who is harmed**, and the **specific design choice** that reduces it. This is the
FMEA judges want — not "we tested it and it works."

| Failure mode | Who gets harmed | Design choice that reduces it |
|---|---|---|
| **Misroute** — answers a different question | The budget analyst makes a timing call on the wrong analysis; ultimately unhoused people if funds are mis-timed | Confidence-gated routing (ask, don't guess) + evaluator question-match + one self-correction retry + visible parsed-intent echo |
| **Param misparse** — wrong $ / years | A decision sized to the wrong number | Unit-aware parser + completeness normalizer (no parsed value dropped) + evaluator parameter-fidelity warn + parameter echo |
| **Individual / sub-CoC profiling** *(worst harm)* | A specific person or neighborhood — surveillance, stigma | Deterministic safety rail forces `out_of_scope` (a crafted prompt cannot override it) + evaluator re-checks scope + **no individual data exists in the system by design** |
| **Invented / altered number** | A fabricated figure drives a real budget | Number-guard (every figure must trace to the engine) + evaluator grounding check → fall back to the deterministic brief |
| **False confidence on a weak city** | An illustrative estimate treated as calibrated truth | Data-confidence check labels non-LA cities "illustrative," widens bands; every brief carries data vintage + per-value confidence |
| **Wrongful refusal (over-caution, F8)** | A legitimate user; the tool looks broken | Evaluator is annotate-first (warn ≠ block); refusal reserved for real scope/data violations; tested for over-refusal |
| **Silent default** — answers an unasked question | User acts on an answer they didn't request | No-default-without-saying-so + parameter echo + clarify on low confidence |

**The headline line for the video and the Devpost field:** *"When our AI is uncertain or wrong, the
user sees exactly why — a per-dimension response check — instead of a confident wrong answer. The
worst outcome in a budget tool is a plausible mistake taken as fact, so we designed the system to
make its errors loud."*

---

## 6. Devpost "Responsible AI Guardrail" field (ready to paste)

> **The risk:** a budget office could act on a confident-looking answer that is actually wrong —
> mis-routed, mis-parsed, or based on a weakly-calibrated city — and mis-time real housing dollars.
> The specific harm lands on unhoused people if funding is delayed on a bad number, and (in the worst
> case) on individuals if the tool were ever used to profile a person.
>
> **What we did:** a dedicated Evaluator agent checks every answer before the user sees it across six
> dimensions — grounding (no invented numbers), scope (no individual-level questions), parameter
> fidelity, data confidence, chart–text consistency, and question-match. Hard guarantees are
> deterministic code; an LLM judge only assesses relevance. When something is off, the system does not
> hide it: it shows a "Response Check" with the specific issue in plain language, asks a clarifying
> question instead of guessing when routers disagree, and refuses (with a suggested reformulation)
> rather than answer an out-of-scope or unsupported question. We make our errors loud.

---

## 7. How it scores, and what to film

- **Responsible AI (10%):** the FMEA + the visible Response Check = a concrete, specific answer, not
  a checkbox.
- **AI Reasoning (35%):** the self-correction loop and confidence-gated routing are visible,
  multi-step reasoning.
- **Impact (15%):** trust — a budget director can *see* when to rely on a number.

**Film:** (1) ask a clean question → green Response Check. (2) ask an ambiguous one → the agent shows
two readings and asks instead of guessing. (3) plant a misroute → the evaluator catches it and
self-corrects on camera. (4) ask an individual-level question → it declines with the privacy reason
and a suggested reformulation. Narrate: *"the worst answer is a confident wrong one — so we built an
agent whose whole job is to catch that."*

---

## 8. Build order (fits the June 21 window)

1. **Deterministic evaluator first (1.5h)** — checks 1–5 reuse existing functions (`numbers_are_grounded`,
   the safety rail, `check_data_support`, the chart-consistency test). Attach `response_check`, render
   the panel. This ships value with zero LLM risk.
2. **Parameter echo + no-silent-default (0.5h)** — surface the parsed reading; flag every default.
3. **Confidence-gated routing (1h)** — run both routers, add `route_confidence`; disagreement → clarify.
4. **LLM question-match + 1-retry self-correction (1.5h)** — the Sonnet judge + the repair loop.
5. **Tests (1h):** misroute → caught + repaired; planted fake number → grounding fail → deterministic
   brief; scope leak → decline; valid question → not over-refused; default used → warned.

Steps 1–2 are independent of the Sonnet migration and safe to do now; steps 3–4 layer onto Phase 1/2
of the migration plan.
