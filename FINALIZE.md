# WaitCost — Finalize Brief (Gemma-default + 4 features)

> **⚠️ HISTORICAL — SUPERSEDED.** This was the Gemma-era build brief. WaitCost has since migrated its brain to **Claude Sonnet 4.6** (planner + narrator), added a 5th agent (the Evaluator), and removed the Gemma/Ollama path entirely. The deterministic `WAITCOST_PLANNER=rule` fallback described here still exists. See `README.md`, `ARCHITECTURE.md`, and `GOVERNANCE.md` for the current system. Kept for provenance only.

**For the coding agent.** Finish the WaitCost backend/agent for the demo: make the local Gemma model
the default planner *and* narrator, and add four features. This file is the spec — read it fully, then
build in the ranked order in §3. The frontend brief is separate (`IMPLEMENTATION.md`); coordinate the
API additions here with it.

---

## 0. Non-negotiable rules
1. **Stay fully offline.** No network calls, no API keys. Gemma runs locally via Ollama
   (`http://localhost:11434`). Public data stays baked in.
2. **The engine owns every number.** Gemma may *route* and *phrase*; it must never invent or alter a
   figure. All headline numbers come from the deterministic Python (`agent/skills.py`, `analysis/`).
3. **The deterministic path must always work.** If Ollama is down or returns junk, everything falls
   back to the rule-based planner and the deterministic brief — silently, no crash. The demo must be
   runnable with `WAITCOST_PLANNER=rule` and zero Ollama.
4. **Keep `pytest eval/verifier.py` green** (39 tests today). Add tests for everything new.

---

## 1. Current state (what already exists — don't rebuild it)
- `agent/planner.py`: `plan(question, params)` chooses by env `WAITCOST_PLANNER` ∈ {`rule` (default),
  `gemma`, `auto`}. `_gemma_plan` calls Ollama (`GEMMA_MODEL=gemma3n:e2b`), JSON-constrained, validates
  intent, **falls back to `_rule_based_plan` on any exception.** `classify_intent` covers 10 intents.
  `explain_brief()` is an optional short Gemma gloss.
- `agent/orchestrator.py`: `WaitCostAgent.answer(question, out_dir, approve_allocation)` runs the loop
  and records **`self.trajectory`** — a list of `{skill, tier, approved}` appended in `_check_tier`
  *as each step runs*. Returns a dict: `plan, intent, direct_answer, recommended_chart, runs,
  comparison, drivers, inflow_model, artifacts, brief_markdown, trajectory` (or a `declined` dict).
  `ACTION_TIERS` maps each skill to Tier 0/1/2; Tier 2 (`optimize_allocation`) needs approval.
- `agent/skills.py`: `write_brief(...)` builds `brief_markdown` deterministically. `compare_*`,
  `retrieve_us_context`, `run_backtest`, etc.
- `api/main.py` + `api/payloads.py`: FastAPI bridge (`/ask`, `/scenario`, `/model`, `/backtest`,
  `/equity`, `/context`, `/charts`, `/chart`, `/cocs`, `/tools`, `/coc-points`, `/geo`). CORS open to
  Vite `:5173`.

---

## 2. Task A — Make Gemma the default (harden it)
**Goal:** Gemma is the primary planner *and* writes the narration, with the rule-based path as an
automatic, invisible safety net.

- In `planner.py`, change the default mode so Gemma is tried first: `_mode()` should default to **`auto`**
  (Gemma-first, auto-fallback) instead of `rule`. Keep `WAITCOST_PLANNER=rule` as an explicit override
  for a guaranteed-deterministic demo, and `=gemma` to force Gemma (error if down).
- Add a tiny **Ollama health check** helper (e.g. `gemma_available()` — GET `/api/tags`, short timeout).
  Use it so `auto` skips the Gemma attempt instantly when Ollama isn't running (no 20s timeout stalls).
- Surface which planner actually ran: the result already carries `plan.planner` (`"gemma"` /
  `"rule_based_fallback"`). Expose it in the API response and show a small "planned by Gemma (local)"
  vs "rule-based" tag in the UI so judges *see* the LLM is live.
- **Docs:** update `README.md` quickstart — `ollama pull gemma3n:e2b`, default is now Gemma-with-fallback,
  and `WAITCOST_PLANNER=rule` for the can't-fail demo mode.
- **Verify:** run the agent (a) with Ollama up → `planner=gemma`; (b) with Ollama stopped → identical
  shape, `planner=rule_based_fallback`, no error. Add a test that monkeypatches the Ollama call to fail
  and asserts graceful fallback.

---

## 3. Features — build in THIS order (ranked by demo payoff vs. risk)

### ① Real streaming agent trajectory (SSE)  — highest payoff (AI Reasoning = 35%), low risk
Make the frontend "thinking" timeline *genuine*: stream each agent step as it executes instead of
returning them all at once.

- Add an optional `on_step` callback to `WaitCostAgent.answer(...)` (call it inside `_check_tier` right
  after appending to `self.trajectory`), passing `{skill, tier, approved}` plus a human label/detail.
- Add a **skill→presentation map** (label + one-line detail + tier) so the stream is readable, e.g.
  `run_simulation → "Running 3 scenarios (Monte Carlo)"`, `run_backtest → "Backtesting against observed 2024"`.
- New endpoint **`POST /ask/stream`** returning `text/event-stream`: run `answer()` (simplest robust
  approach: in a background thread writing step events to a thread-safe `queue.Queue`; the SSE generator
  drains the queue). Emit one `event: step` per step `{label, tier, detail, status:"running"|"done"}`,
  pause-flag any Tier-2 step, then a final `event: result` with the full payload `/ask` returns today.
- Keep the existing synchronous `/ask` as the fallback the frontend uses if SSE fails.
- Frontend: consume with `EventSource`; render steps with the existing tier badges; show the Tier-2 pause.
- **Test:** hit `/ask/stream`, assert the event sequence ends with a `result` event whose numbers equal
  the synchronous `/ask` for the same question (determinism check).

### ② Export decision brief to PDF / Word — high polish, low risk
A tangible artifact judges keep.

- Backend endpoint **`GET /brief/export?format=pdf|docx&question=…&coc=…&approve_allocation=`**: run the
  agent, then render `brief_markdown` + the headline number/range + the recommended chart image + the
  source lines + the standing disclaimer into a clean one-page file. Use **`python-docx`** for docx and
  **`reportlab`** (or `weasyprint`) for pdf — both offline. Return as a file download
  (`Content-Disposition: attachment`).
- Reuse the engine's real figures; do not re-compute differently. Include "Generated by WaitCost ·
  HUD 2024 PIT · Census ACS 2024 (API) · figures are ranges" footer.
- Frontend: a "Download brief (PDF/Word)" button on the Ask answer card.
- Add `python-docx` and `reportlab` to `requirements.txt`. **Test:** endpoint returns a non-empty file of
  the right MIME type and the headline figure string appears in the docx text.

### ③ Gemma-written decision brief — high payoff, medium risk (guard the numbers)
Let the local LLM write the one-page memo from the engine's numbers, so the narration reads like an
analyst — while staying truthful.

- Add `planner.narrate_brief(facts: dict) -> str | None`: prompt Gemma with the **computed facts**
  (headline cost + 80% range, status-quo cost, savings, intent, city, top SHAP driver, backtest error,
  the disclaimer) and ask it to write a short policy memo. Temperature ≤ 0.2. Return `None` on any error.
- **Number guard (critical):** before accepting Gemma's text, verify every `$`/number it emits is one of
  the figures you passed in (extract numbers via regex; reject if it introduces an unseen figure). On
  rejection or `None`, **fall back to the deterministic `write_brief` markdown.** Never show unguarded LLM numbers.
- Wire it into the output so `brief_markdown` is the Gemma version when available+valid, else the
  deterministic one. Tag which was used (e.g. `brief_author: "gemma" | "deterministic"`).
- **Test:** feed facts, monkeypatch Gemma to return text containing a fabricated number → assert the
  guard rejects and the deterministic brief is used.

### ④ Two-city comparison — nice insight, build last / if time (Impact & Insight = 15%)
Run the same question across two cities side by side.

- Endpoint **`POST /compare-cities`** `{question?: str, budget_musd, delay_years, coc_a, coc_b}`: build
  params for each via `model.coc_registry.build_params_for_coc`, run the engine for both, return
  `{a: <result>, b: <result>, delta: {cost_of_waiting_musd, rate_per_1k, …}}`. Population-level only.
- Frontend: a compact side-by-side (e.g. LA vs Chicago) — two answer cards + a small delta line, and/or
  extend the Visualize "city benchmark" chart. Reuse existing components.
- **Test:** `/compare-cities` with CA-600 vs IL-510 returns both blocks and a numeric delta.

---

## 4. Cross-cutting
- Update `requirements.txt` (sse via FastAPI `StreamingResponse` needs nothing extra; add `python-docx`,
  `reportlab`). Update `README.md` + `ARCHITECTURE.md` (new endpoints, Gemma-default, the brief author tag).
- Extend `eval/verifier.py` with the tests named above; keep the whole suite green. (Note: the full suite
  is ~40s; run with `-k` splits if your sandbox times out.)
- Every new endpoint must degrade gracefully offline and never leak data off-machine.

## 5. Definition of done
- Default run uses Gemma when Ollama is up (`planner=gemma`, brief authored by Gemma & number-guarded),
  and is byte-stable to the deterministic path when Ollama is down.
- `/ask/stream` streams readable, tier-badged steps and ends with a result equal to `/ask`.
- Brief downloads as PDF and Word with the real headline + range + sources + disclaimer.
- `/compare-cities` returns two cities + a delta (if built).
- `pytest eval/verifier.py` green; README/ARCHITECTURE updated; nothing leaves the machine.

## 6. Don'ts
Don't let the LLM emit any number not produced by the engine · don't remove the rule-based/deterministic
fallback · don't make the demo depend on Ollama (keep `WAITCOST_PLANNER=rule` working) · don't add
individual- or neighborhood-level data · don't break the existing tests or endpoints.

## 7. Honest note on scope
These are the right additions **if time allows**, ranked above by payoff. The win is mostly polish +
story now — build ①②, then ③, and treat ④ as optional. Stop adding features once the 3-minute demo
runs clean.
