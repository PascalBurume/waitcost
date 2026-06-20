# WaitCost — Migration Plan: Offline Gemma → Claude Sonnet 4.6

USAII Global AI Hackathon 2026 · Challenge 6A. Goal: maximize **AI Reasoning (35%)**
and **Solution Design (20%)** without losing the guardrails that win **Responsible AI (10%)**.

---

## TL;DR

Swap the *brain*, keep the *cage*. Claude Sonnet 4.6 (`claude-sonnet-4-6`) becomes the
default planner, narrator, and — the big upgrade — a real **tool-using agent** that
orchestrates the engine in multiple reasoning steps. Every guardrail stays exactly where
it is: the engine still owns every number (number-guard), a human still owns every dollar
(Tier-2 gate), and individual-level questions are still refused (deterministic safety rail).
Offline Gemma is **kept as a fallback**, not deleted — which converts "we lost offline" into
"frontier reasoning by default, with an air-gapped private mode." That is a stronger story
than either model alone.

---

## The strategic call: hybrid, not rip-and-replace

**Recommendation: keep all three planner modes and add Claude as the default.**
Your `plan()` already dispatches on `WAITCOST_PLANNER ∈ {rule, gemma, auto}`. We add `claude`
and make the degradation chain **Claude → Gemma → rule**. Cost of keeping Gemma: ~zero (the
code already exists). Benefit: three things judges reward —

- **Graceful degradation / lifecycle thinking** (the grad differentiator): a live cloud brain,
  an offline local brain, and a deterministic rule brain — same output shape, automatic failover.
- **A can't-fail demo**: `WAITCOST_PLANNER=rule` still runs with no network, no key. You never
  bet the demo on an API call.
- **The privacy answer**: "Claude by default; flip one env var for a fully offline, air-gapped
  deployment." You don't *lose* the offline story — you make it a deployment option.

If you genuinely want to delete Gemma, say so and I'll cut it — but I'd keep it.

---

## What changes vs. what stays

| Stays (do not touch) | Changes (upgrade) |
|---|---|
| The deterministic engine owns every number | The planner/brain: Gemma → Claude Sonnet 4.6 |
| Number-guard rejects any invented figure | One-shot intent → **multi-step tool-use loop** |
| Tier-2 human-approval gate | Static "thinking" log → **streamed real reasoning** |
| Safety rail forces `out_of_scope` | Brief prose quality (Claude writes far better memos) |
| Decline-on-thin-data (`check_data_support`) | Routing accuracy (Claude ≥ today's 99%) |
| Every figure is a range, never a point | Offline-only → **hybrid** (Claude default, Gemma fallback) |
| The capability registry as single source of truth | Registry now also emits **Anthropic tool schemas** |

The elegance: in `plan()`, the LLM's output already passes through `_apply_safety_rail()` and
`_normalize_calls()` before anyone uses it. Those rails veto and complete *whatever* the model
proposes. So swapping the model in is **safe by construction** — the guardrails sit downstream
of the brain.

---

## Phase 1 — Drop-in brain swap (the can't-fail upgrade, ~2–3h)

Lowest risk, immediate payoff. No behavior change except a smarter planner and nicer prose.

**1. Provider abstraction.** Add `agent/llm.py` with one function:
`generate(system, prompt, *, json=False, temperature=0.0, max_tokens=512) -> str`.
It routes by mode: `claude` → Anthropic SDK; `gemma`/offline → the existing `_ollama_generate`.
Mirrors what `planner._ollama_generate` already does, so callers don't care who answered.

**2. `_claude_plan(question, params)`** mirroring `_gemma_plan` — same return dict
(`intent, delay_years, budget_musd, budgets, mix, scenarios, planner="claude"`). Reuse
`build_plan_system(default)` verbatim (the registry-derived prompt). Pass it as the Anthropic
`system` param, request strict JSON, `temperature=0`. Validate `intent ∈ INTENTS` exactly as
today; on miss, defer to `classify_intent` (rules disambiguate). The safety rail + normalizer
already wrap it in `plan()`.

**3. Mode + failover.** `_mode()` default stays `auto`, but `auto` now tries Claude first
(`claude_available()` = key present), then Gemma (`gemma_available()`), then rule — each in a
try/except so it never stalls or crashes. `WAITCOST_PLANNER=claude` forces Claude (errors loudly,
to prove the path on camera); `=gemma` and `=rule` unchanged.

**4. Number-guarded narration.** Point `narrate_brief`, `narrate_grounded`, `explain_brief` at
`agent/llm.generate` instead of `_ollama_generate`. The guard (`numbers_are_grounded`) is
unchanged and now protects against a *more* fluent writer — exactly when you want it.

**5. Surface it.** The result already carries `plan.planner`; expose "planned by Claude Sonnet 4.6"
vs "offline Gemma" vs "rule-based" as a UI/brief tag so judges *see* which brain ran.

**Done = Phase 1:** same tests green, routing benchmark ≥ today, briefs read like an analyst wrote
them, and pulling the plug (`=rule`) still works offline.

---

## Phase 2 — Real agentic reasoning (the 35% win, ~3–4h)

This is what turns "an LLM that picks one label" into "an agent that reasons." It is the single
highest-scoring change.

**Tools from the registry.** Add `caps.anthropic_tools()` that converts each engine capability
in `specs.py` into an Anthropic tool: `name=intent`, `description=when_to_use`,
`input_schema` derived from `params` (`budget_musd`, `delay_years`, `budgets`, `coc`). The
handler in `agent/handlers.py` is the executor. One registry, three consumers now (rule regex,
Gemma prompt, **Claude tools**) — still no drift.

**The loop** (`WAITCOST_AGENT=toolloop` in the orchestrator): give Claude the tools + a tight
system prompt ("you analyze a homelessness cost-of-inaction simulator; call tools for every
number; never compute figures yourself"). Claude calls a tool → the orchestrator runs the **real
deterministic handler** → returns the result → Claude reasons and may chain more (e.g.
`cost_of_waiting` → `uncertainty` → `compare_budgets`) → then writes the brief. Because every
number comes back from a tool = the engine, figures are grounded **by construction**, and the
number-guard becomes a belt-and-suspenders second check.

**Extended thinking.** Enable Sonnet's thinking for the planning/decision turn with a capped
budget; surface a 2–3 line thinking *summary* in `self.trajectory`. That is the "where's the AI?"
moment on camera — visible, genuine, multi-step reasoning, not a canned log.

**Tier-2 inside the loop.** When Claude calls the Tier-2 tool (`optimize_allocation` / recommend
spend), the orchestrator intercepts *before executing*, raises the existing `TierViolation`, and
pauses for human approval. Now the gate is even more compelling: the agent *wanted* to act and
the design stopped it. Keep the `_check_tier` trajectory logging; stream it.

**Determinism guard for the demo:** `temperature=0`, fixed tool order tie-breaks, and the engine
itself is seeded — so the dollar figures are identical run-to-run even though the prose varies.

---

## Phase 3 — The four agents, for real (~2h, if time)

Make the "4 agents" literal instead of nominal:

- **Analyst** = the Phase-2 supervisor (the tool loop).
- **Decision** (`agent/decision.py`) = a specialized Claude call that reasons about the *direction*
  confidence vs the dollar *magnitude* (the framing people misread), number-guarded — leads the brief.
- **CityBrief** (`agent/city_brief.py`) = a specialized call for qualitative `city_situation`/`care_plan`,
  grounded in the cited source registry via `narrate_grounded` (no invented stats).
- **Visualization** (`analysis/viz.py`) = exposed to the supervisor as a `pick_chart` tool so the
  agent chooses the decision chart, then the chart is built from the same engine output.

Pattern stays: **LLM plans & orchestrates, deterministic code executes, tiers gate, memory records.**

---

## Guardrails we KEEP — and why they matter *more* now

A stronger brain raises the stakes, so the cage is the story:

- **Number-guard** (`numbers_are_grounded`): every figure in any prose must appear in the engine
  facts; else fall back to the deterministic brief. Add a test that feeds Claude a fabricated number
  and asserts rejection (mirror the existing Gemma test).
- **Safety rail** (`_apply_safety_rail`): individual/sub-CoC questions are forced to `out_of_scope`
  regardless of what Claude says — a crafted prompt cannot override it (F4 robustness).
- **Tier-2 gate**: recommending an allocation always pauses for a human.
- **Decline-on-thin-data**, **ranges on every dollar**, **data vintage in every brief** — unchanged.

---

## The responsible-AI reframe (turn the trade-off into a win)

Say this out loud in the video; it neutralizes the "but it's not offline anymore" critique:

1. **No PII is even possible.** The system holds only public, aggregate HUD/Census data; the
   safety rail forbids individual-level questions. So nothing sensitive can ever be sent to any API —
   by design, not by promise.
2. **Three-tier autonomy of *models*, not just actions.** Claude (cloud, best reasoning) → Gemma
   (offline, private) → rule (deterministic, reproducible). One env var moves between them.
3. **The brain got smarter; the leash got no longer.** Frontier reasoning, but the engine still owns
   every number and a human still owns every dollar.

That maps cleanly to the rubric: Reasoning ↑ (tool loop + thinking), Solution Design ↑ (failover
architecture), Responsible AI held (guardrails + the PII-by-design argument).

---

## Config, dependencies, secrets

- `pip install anthropic` → add to `requirements.txt` (pinned).
- `ANTHROPIC_API_KEY` via env only — **never commit it**; document in README.
- Model string: `claude-sonnet-4-6`. Knobs: `max_tokens`, `thinking.budget_tokens`, `temperature=0`,
  request timeout + 1 retry, then fail over to Gemma/rule.
- New env: `WAITCOST_PLANNER=claude|auto|gemma|rule`, optional `WAITCOST_AGENT=toolloop|single`.

---

## Eval & testing (keep the suite green)

- Re-run `eval/routing_benchmark.py` on Claude; gate at ≥ today's 99% (expect a clean 100% on the
  clear+paraphrase tier).
- New tests: (a) fabricated-number → guard rejects → deterministic brief; (b) Claude unreachable →
  fails over to Gemma then rule, identical output shape; (c) tool-loop result equals the synchronous
  `/ask` numbers (determinism); (d) Tier-2 tool call → `TierViolation` before execution.
- `eval/chart_coverage.py` and the 101 deterministic tests stay green (engine untouched).

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Network/API down during the live demo | `WAITCOST_PLANNER=rule` is the guaranteed take; record a fallback pass; cache a canned response |
| API key leakage | env-only, `.gitignore`, never in code or video |
| Latency from thinking + tool loop | cap `thinking.budget_tokens`, pre-warm, stream so it *looks* like reasoning (it is) |
| Cost | negligible at demo scale; note it for honesty |
| Non-determinism in prose | `temperature=0`; numbers come from the seeded engine, not the model |

---

## Timeline to June 21 (hour-budgeted)

- **Block A (2–3h) — Phase 1.** Provider abstraction, `_claude_plan`, failover, narration swap,
  README + key docs, tests green. **Ship this first; it alone is a real upgrade.**
- **Block B (3–4h) — Phase 2.** Registry→tools, the tool-use loop, streamed trajectory, extended-
  thinking summary, Tier-2 interception. This is the 35% lever.
- **Block C (2h) — Phase 3.** Decision + CityBrief sub-agents; `pick_chart` tool.
- **Block D (2h) — Prove it.** Re-run evals, update `ARCHITECTURE.md`/`README.md`/`VIDEO_NOTES.md`,
  record the demo. Keep Streamlit + rule mode as the safety net.
- **Buffer** before the 11:59 PM ET deadline.

Stop-loss: if Block B runs long, ship Phase 1 + a hand-scripted two-step reasoning demo. Never
sacrifice a green test suite or the deterministic fallback to chase Phase 3.

---

## What to film (so the upgrade scores)

1. Ask a question; show the **streamed reasoning** — Claude calling `cost_of_waiting`, then
   `uncertainty`, then writing the memo. Say "the agent chose those steps."
2. Show the **number-guard** rejecting a planted fabricated figure → deterministic brief used.
3. Trigger the **Tier-2** path → the agent is stopped, a human approves. "Frontier reasoning;
   the engine owns every number; a human owns every dollar."
4. Flip `WAITCOST_PLANNER=gemma` → same answer, fully offline. "And it still runs air-gapped."

---

## Decision points for you

1. **Hybrid vs. full replace?** I recommend hybrid (keep Gemma as fallback). Say the word to cut it.
2. **How far in the time we have?** I'd commit to Phase 1 + Phase 2; treat Phase 3 as a stretch.
3. **Want me to start now?** I can implement Phase 1 end-to-end (provider abstraction, `_claude_plan`,
   failover, narration swap, tests) and verify the suite stays green — then we tackle the tool loop.
