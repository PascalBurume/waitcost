# WaitCost — Architecture (one page, for the team)

## The one rule
**The engine is the asset; the UI is disposable.** All math lives in the Python
package (`model/`, `analysis/`, `agent/`). Every front end — the React/TypeScript
app and the Streamlit app — only *calls* the engine and *draws* results. No front
end ever computes a number. That's why the agent, the Streamlit app, and the web
app can never disagree, and why every figure is traceable to a simulation output.

```
                ┌──────────────────────────── ENGINE (Python) ───────────────────────────┐
                │  model/      simulate · montecarlo · cost (+composition) · backtest      │
                │  analysis/   cost-of-waiting (+sweep) · break-even · sensitivity ·        │
                │              effect band · cost_composition · viz (19 chart builders)     │
                │  agent/      4 agents · capability registry · tool-calling planner        │
                │              (Gemma/​rule) · orchestrator (front door) · handlers ·        │
                │              retrieval (concept_qa, data_lookup) · city_brief · decision  │
                │  config/params.yaml · data/coc_panel.csv · data/concepts.json ·           │
                │  model/inflow_model.json                                                  │
                └───────▲───────────────────────▲──────────────────────────▲──────────────┘
                        │ same skills           │ same skills              │ same skills
            ┌───────────┴─────┐      ┌──────────┴──────────┐     ┌─────────┴───────────┐
            │ Streamlit app   │      │ FastAPI bridge      │     │ run_demo.py / eval  │
            │ app/dashboard.py│      │ api/main.py         │     │ (CLI + 112 pytest)  │
            └─────────────────┘      └─────────▲───────────┘     └─────────────────────┘
                                               │ JSON over HTTP
                                     ┌─────────┴───────────┐
                                     │ React + TypeScript  │  (Vite app: Ask, Explore,
                                     │ frontend/           │   Visualize, Where's the AI,
                                     └─────────────────────┘   Equity, Governance, Map)
```

## Four agents (one front door)
The orchestrator (`agent/orchestrator.py`) is the single entry point (`/ask`); it
classifies the question and either runs the analytic loop, calls a retrieval tool,
or hands off to a specialist. Counts come from the code registry
(`agent/tools.py` → `/tools`): **4 agents · 20 capabilities · 19 chart builders.**

- **Analyst agent** (`agent/orchestrator.py`) — the loop below: plan → call the
  deterministic tools → narrate → log to `MEMORY.md`. Autonomy is bounded by Action
  Tiers (0–1 automatic; Tier 2 — recommending an allocation — needs human approval).
- **Visualization agent** (`analysis/viz.py`) — picks the right decision chart for the
  question and builds a render-ready spec from real engine output (**19 builders**),
  including the cost-of-waiting waterfall, the **per-budget sweep** chart, the
  divergence trajectory, and the **cost-composition donut**.
- **City Brief agent** (`agent/city_brief.py`) — answers *qualitative* questions
  (`city_situation` / `care_plan`) from a curated, cited source registry
  (`data/city_sources.json`) + the engine's indicators; offline by default.
- **Decision agent** (`agent/decision.py`) — turns raw scenarios into a plain-English
  recommendation (the act-now / wait call + a confidence on the *direction*),
  number-guarded; it rides along in every analytic answer and leads the decision brief.

Every analysis type is declared once in the **capability registry**
(`agent/capabilities/specs.py`): its `when-to-use`, regex triggers, tier, handler, and
chart. `planner`, the orchestrator's dispatch, `tools.CAPABILITIES`, and `viz.INTENT_CHART`
are all *derived* from it, so they can't drift. Adding a capability = one `register(...)`
+ one handler; `QUESTIONS.md` and the Gemma prompt regenerate from the same registry.

## The tool-calling router (one question → a list of typed calls)
The planner no longer maps a question to a single intent — it produces a **list of
tool calls**, so the router can answer "do this for several inputs," "answer two
different things," or "this is a concept question, not a calculation."

```
plan = {
  "calls": [ {"tool": <intent>, "args": {"budget_musd":15, "delay_years":3}}, … ],
  "parsed_params": {"budgets":[…], "delays":[…]},   # deterministic backstop
  "coverage_notes": [ … ],                          # explicit, never silent
  # legacy mirror (intent/budget_musd/delay_years/budgets) derived from calls[0]
}
```

- **LLM proposes, a deterministic rule completes/vetoes.** After the planner (Gemma or
  rule) runs, `planner._normalize_calls` re-reads the raw question for *all* parameters
  (`_distinct_budgets`, `_extract_delays`), so it doesn't depend on the LLM being up.
- **Compound questions fan out.** "Wait 3y on a $1M **and** $15M program" → two
  `cost_of_waiting` calls (cardinality is *N calls*, not list args). "…and…" answers
  each; an explicit "which is better?" cue keeps the single `compare_budgets` analysis.
- **No-silent-drop guarantee.** Every parsed value must appear in a call or an explicit
  `coverage_note`. Validation clamps/dedupes budgets and caps the call count.
- **Safety rail first.** Individual / sub-CoC profiling is forced to a single
  `out_of_scope` call regardless of what the LLM proposed.
- **Executor + synthesizer** (`orchestrator.answer`): the primary call drives the full
  pipeline; extra same-tool calls are computed and folded into one answer (per-budget
  rows + the `cost_of_waiting_by_budget` chart). Single-call path is byte-identical to
  before — the 112 tests prove it.

## Retrieval tools (cited, offline — not the cost model)
Two `kind=retrieval` capabilities answer questions that are *not* a calculation, from
cited local sources, with **no engine run** and a "general context" label:
- **`concept_qa`** (`agent/retrieval.py` + `data/concepts.json`) — "what is rapid
  re-housing?", "why does housing cost drive homelessness?" Definitions are
  number-guarded; Gemma may only rephrase the curated, cited text.
- **`data_lookup`** — "what data is this based on?", "how recent is the PIT count?" —
  answered from `config/params.yaml` provenance + `data/SOURCES.md`, with citations.

## How the analyst coordinates a task (the loop)
1. **Plan** — `planner.plan()` → a list of typed tool calls (+ `parsed_params`, coverage).
2. **Acquire** — load params, **`check_data_support()`** (decline if too thin / sub-CoC / synthetic).
3. **Route** — retrieval tool (cited, no engine), City Brief hand-off, or the analytic loop.
4. **Reason** — run 3 scenarios (Monte Carlo) → compare → sensitivity → **backtest** → effect band.
5. **Execute** — run any extra calls (e.g. each budget); **synthesize** one answer.
6. **Decide** — the **decision agent** frames the act-now / wait call (number-guarded).
7. **Gate** — recommending an allocation is **Tier 2** → stop and ask a human (`TierViolation`).
8. **Report** — `write_brief()` emits .md/.json/.csv (decision leads, Gemma phrases) → **Remember** (`MEMORY.md`).

Pattern: **LLM plans a call list, deterministic code completes/executes, tiers gate, memory records.**

## The two AI models (deliberately different)
- **Agent brain / language** → an LLM, run **offline** (Gemma `gemma4:e2b` via Ollama), and the
  **default** (`WAITCOST_PLANNER=auto`, Gemma-first with a silent rule-based fallback;
  `=rule` forces the deterministic path, `=gemma` forces the LLM). It (a) parses the
  question into a plan and (b) **writes the one-page brief** from the engine's computed
  facts — but a regex number-guard rejects any figure it didn't receive, so the LLM
  phrases, the engine owns every number. No API key, no data leaves the machine.
- **Prediction (ACS → homelessness)** → **classical, interpretable ML (gradient-boosted
  stumps / Ridge)** with exact SHAP, chosen by leave-one-CoC-out CV because n≈17 (deep
  learning would overfit). Bayesian (PyMC) is the documented stretch.

## Charts that make the decision visible (engine-computed)
- **Cost-of-waiting waterfall** — the act-now bill + the floating cost-of-waiting slice.
- **Per-budget sweep** (`cost_of_waiting_by_budget`) — one bar per program size for a
  compound question; matches the per-budget answer text.
- **Divergence trajectory** ("What your decision is worth") — extra cost vs. an act-now
  $0 baseline, by year, from **paired Monte-Carlo differences** (same-seed draws), so the
  decision's growing value is visible where absolute totals overlap.
- **Cost-composition donut** ("Where your program's cost goes") — the chosen program's
  10-yr cost split by group (chronic / sheltered / unsheltered / at-risk), scaled to the
  Monte-Carlo P50, with a live "saves vs. doing nothing" bar; **reacts to the sliders**.

## Run it
```bash
pip install -r requirements.txt
ollama pull gemma4:e2b                                            # offline planner + narrator
python run_demo.py "What if we wait 3 years on a $15M program?"   # CLI agent
pytest eval/verifier.py eval/test_*.py -q                         # 112 deterministic tests
python eval/routing_benchmark.py                                  # routing accuracy (must-pass 100%)
python scripts/gen_questions.py                                   # regenerate QUESTIONS.md from the registry
python scripts/fetch_acs.py                                       # reproducible ACS pull (verified 0/119 ≥5%)
python scripts/train_inflow.py                                    # train inflow model + SHAP
streamlit run app/dashboard.py                                    # Streamlit UI
cd frontend && npm run dev                                        # React/Vite UI (port 5173)
uvicorn api.main:app --reload --port 8000                         # JSON bridge -> /docs
export WAITCOST_PLANNER=rule    # opt out to the can't-fail, Ollama-free demo
```

## API endpoints (for the React frontend)
`GET /health · GET /params · POST /ask · POST /ask/stream (SSE; final result identical
to /ask) · GET /brief/export (?format=pdf|docx) · POST /compare-cities · POST /scenario
(now also returns `divergence` — paired-MC extra-cost-vs-acting-now by year — and
`composition` — the program's cost split by group + saves-vs-nothing) · GET /effect-band ·
GET /model · GET /backtest · GET /coc-points · GET /geo · GET /context · GET /equity ·
GET /charts · GET /chart (now accepts `budgets=1,15` for the per-budget sweep chart) ·
GET /cocs · GET /tools`
Open `http://localhost:8000/docs`. `/ask` carries `planner` (`gemma`/`rule_based_fallback`)
and `brief_author` so the UI can tag whether the LLM is live; engine answers also carry
`plan.calls`, `sweep` (per-budget rows), and `coverage_notes`.

## Status
Engine + Streamlit + **React/Vite frontend** + FastAPI bridge are all live and demoable.
**Safety net:** the deterministic `rule` planner + Streamlit app are the guaranteed,
offline, can't-fail demo. Never delete what works to chase an upgrade.
