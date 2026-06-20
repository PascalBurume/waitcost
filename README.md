---
title: WaitCost
emoji: ⏳
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

<!-- The YAML above configures the Hugging Face Space (Docker SDK, single service on
     port 7860). It is ignored when this README renders on GitHub. Deploy steps: DEPLOY_HF.md -->

# WaitCost — The Cost of Doing Nothing (Agents + Simulator)

USAII Global AI Hackathon 2026 · Graduate Track · Challenge 6, Direction A.

A **multi-agent policy-analyst system** on top of a system-dynamics simulator.
Ask a plain-English question about *delaying* homelessness intervention; the
agent classifies the question, runs calibrated simulations with uncertainty,
explains the drivers, picks the right chart, and writes a decision brief —
stopping short of any binding allocation, which stays with a human.

Calibrated for **CA-600 Los Angeles** on real public data; the same trained
model scores **17 US cities**.

## Quickstart

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...                                  # Claude planner + narrator (default)
python run_demo.py "What if we wait 3 years on a $15M program?"   # CLI agent
pytest -q                                                         # deterministic test suite
python eval/routing_benchmark.py                                  # 108-Q routing accuracy report
python eval/chart_coverage.py                                     # every question -> a buildable chart
streamlit run app/dashboard.py                                    # interactive dashboard (5 tabs)
uvicorn api.main:app --reload --port 8000                         # JSON API -> http://localhost:8000/docs
```

**Claude Sonnet 4.6 is the default brain.** It plans and narrates via the
Anthropic API — but no PII is even possible (the system holds only public,
aggregate HUD/Census data and refuses individual-level questions), so nothing
sensitive can ever be sent. The planner runs in mode `WAITCOST_PLANNER` ∈:

- `auto` *(default)* — Claude when a key is present; if there's no key or the API
  errors it falls back to the rule-based planner **silently** (never stalls,
  never crashes). The result carries `planner` (`claude` / `rule_based_fallback`)
  and `brief_author` (`claude` / `deterministic`) so you can *see* which brain ran.
- `rule` — pure deterministic, never touches the network (**the air-gapped,
  can't-fail demo mode**).
- `claude` — force Claude (errors loudly if the API is unreachable — to prove the path).

```bash
export WAITCOST_PLANNER=rule    # guaranteed-reproducible, network-free demo
export WAITCOST_AGENT=toolloop  # (opt-in) Claude orchestrates the engine over multiple tool calls
```

Claude (a) routes the question into a plan and (b) writes the one-page brief — but
**every number stays the engine's**: a regex number-guard rejects any figure the
model emits that the engine didn't compute, falling back to the deterministic
brief. The model never invents or alters a headline figure.

## Routing — a layered router (LLM proposes, rules veto)

Understanding *which* question a user is asking is the job we put the model on:

1. **Claude (primary)** — in `auto`/`claude` mode Claude classifies the intent
   *semantically* from the registry's `when_to_use` + contrastive few-shots, so it
   disambiguates things keywords can't ("the ROI of the city's **plan**" → `roi`,
   not `care_plan`).
2. **Deterministic safety rail (authoritative)** — individual / sub-CoC profiling is
   forced to `out_of_scope` no matter what the model says. The "never profile
   individuals" promise cannot depend on the LLM (`planner._apply_safety_rail`).
3. **Rule fallback (reproducible)** — a registry-ordered regex walk when no key is
   set, and the can't-fail demo mode. An unknown LLM label defers to it, not to a
   blind default.

Routing quality is **measured**, not assumed: a ~100-question, judge-style benchmark
(`eval/routing_cases.py`) scores accuracy with a regression gate —
**100% on the clear+paraphrase tier, 99% overall** in rule mode
(`python eval/routing_benchmark.py`). And every question type yields a render-ready
graphic — `eval/chart_coverage.py` proves 108/108 questions build a valid chart.

## Five agents

- **Analyst agent** (`agent/orchestrator.py`) — the loop: classify the question →
  call the right tools (the "sandbox" of deterministic Python) → narrate → log to
  `MEMORY.md`. Autonomy is bounded by **Action Tiers**: Tier 0–1 automatic; Tier 2
  (recommending an allocation) needs human approval. Declines out-of-scope or
  thin-data questions instead of guessing.
- **Visualization agent** (`analysis/viz.py`) — picks the right decision chart for
  the question and builds a render-ready spec from real engine output (18 charts).
- **City Brief agent** (`agent/city_brief.py`) — answers *qualitative* questions
  ("what's the situation in Seattle?", "what is San Diego's plan?") from a curated,
  cited source registry (`data/city_sources.json`) + the engine's own indicators.
  Numbers come only from the engine, narrative + strategy only from cited sources;
  every brief is labelled **"general context — not the calibrated cost model."**
  Offline by default; an opt-in `WAITCOST_ONLINE=1` flag can refresh from the plan URL.
- **Decision agent** (`agent/decision.py`) — turns the simulator's raw scenarios into a
  **plain-English recommendation** a non-technical director can act on: the call (act now /
  wait) with a confidence on the *direction* (separate from the dollar magnitude), and the
  framing people misread — the multi-billion 10-year baseline is mostly unavoidable; the
  timing decision only moves the smaller *cost-of-waiting* slice. It invents no figure
  (number-guarded); it rides along in every analytic answer and leads the decision brief.
- **Evaluator agent** (`agent/evaluator.py`) — the post-answer critic that checks **every
  answer before the user sees it**, across six dimensions (grounding, scope, parameter
  fidelity, data confidence, chart↔text consistency, and an LLM question-match judge). It
  can only flag / annotate / repair / decline — never alter an engine number. On a hard
  failure it triggers a bounded **1-retry self-correction**, then declines rather than show
  a confident wrong answer; uncertainty becomes a *warn* (a caveat), not a wrongful refusal.
  Its verdict ships to the UI as a per-dimension **Response Check**. With confidence-gated
  routing, when the LLM and rule routers disagree at low confidence the system **asks
  instead of guessing** (`clarify`). See [EVALUATOR_AND_GUARDRAILS.md](EVALUATOR_AND_GUARDRAILS.md).

The orchestrator is the single front door (`/ask`): quantitative questions run the
simulator; `city_situation` / `care_plan` questions are handed off to the City Brief agent.

Registry of capabilities is explicit (`agent/tools.py`, exposed at `/tools`):
**5 agents · 16 capabilities · 16 skills · 18 charts.**

The planner is a **tool-calling router**: one question becomes a *list* of typed
calls (`plan.calls`), so compound asks fan out (e.g. "$1M **and** $15M" → two
cost-of-waiting calls) and a deterministic normalizer guarantees **no parsed value
is ever silently dropped**. See [ARCHITECTURE.md](ARCHITECTURE.md).

## One capability registry (Agent-Skills-style)

Every answerable question type is declared once in `agent/capabilities/specs.py`
(its `when-to-use`, regex triggers, tier, handler, and chart). The structures that
used to be hand-maintained in five places — `planner.INTENTS`, `classify_intent`,
the Claude `_PLAN_SYS` planner prompt, the orchestrator's intent dispatch,
`tools.CAPABILITIES`, the **Anthropic tool schemas** (`caps.anthropic_tools()`), and
`viz.INTENT_CHART` — are now *derived* from that registry, so they can't drift.
Adding an analysis means one registry entry + one handler in `agent/handlers.py`.

## Run it as an installable Agent Skill

The engine is also packaged as an Anthropic [Agent Skill](https://github.com/anthropics/skills)
so Claude Code / the Skills API can drive it directly — offline, deterministic, and
with the Tier-2 human-approval gate and number-guard preserved in code:

```bash
python skills/waitcost/scripts/waitcost_cli.py ask "What if we wait 3 years on a $15M program?" --coc CA-600
```

See `skills/waitcost/SKILL.md`. The CLI is a thin wrapper over `api/payloads.py`,
so the skill, the API, and the agent can never disagree on a number.

## What it answers (multi-question intents)

📋 **[QUESTIONS.md](QUESTIONS.md)** is the full, copy-pasteable list of everything you can ask
(auto-generated from the registry: `python scripts/gen_questions.py`).

cost-of-waiting (incl. **multi-budget sweeps**) · break-even · savings-vs-nothing ·
outcome-at-horizon · compare-budgets · compare-mix · sensitivity · **ROI / benefit–cost** ·
**cost-per-person + people-helped** · **regional (multi-city ranking)** ·
**uncertainty / explain-this-number** · city-context · **equity** (racial
disparities, population-level — never individual) · **concept_qa** (define a concept,
cited, no engine) · **data_lookup** (data source / vintage / methodology, cited) ·
greeting/meta → friendly guide · unmapped in-scope → clarify · out-of-scope → declines.
Each answer's recommended chart shows the same figure the text states (numbers are
identical, not re-sampled).

## The AI inside

- **Learned inflow model** (`model/inflow_model.py`): Ridge on real Census ACS →
  HUD PIT across 17 cities, leave-one-CoC-out R²≈0.45, **exact additive SHAP**
  (housing cost is the top driver). Sets the simulator's inflow + its uncertainty.
- **Face-validity backtest** (`model/backtest.py`): seed real 2023 PIT, reproduce
  observed 2024 within band (~4% error for CA-600).
- **Claude Sonnet 4.6 planner + narrator** for natural-language understanding,
  number-guarded prose, and (opt-in `WAITCOST_AGENT=toolloop`) a real tool-use loop
  that orchestrates the engine over multiple steps — with a deterministic rule
  fallback so the demo never depends on the network.

## Data — all real, all sourced (see `data/SOURCES.md`)

- Homeless counts: HUD 2024 PIT CoC Population & Subpopulation reports.
- Economic signals: US Census ACS 2024 1-yr.
- Flow rates (CA-600): HUD System Performance Measures FY2023.
- Per-person costs: Economic Roundtable "Where We Sleep" (2024$).

The ACS economic features are **reproducible from the official Census API with one command**
(`CENSUS_API_KEY=… python scripts/fetch_acs.py`) and **independently verified**: re-fetching from the
live API matched the panel exactly — 0 of 119 values differed by ≥5%. See `data_sources/METHODOLOGY.md`.

## Layout

```
config/params.yaml      calibrated CA-600 assumptions (source + confidence per value)
model/                  simulate · montecarlo · cost · interventions · inflow_model · backtest · coc_registry · states
analysis/               metrics (cost-of-waiting, break-even, compare, sensitivity) · viz (charts) · equity
agent/                  skills (tools) · planner (Claude + rule fallback) · llm (Anthropic provider seam) · orchestrator (loop) · tools (registry)
api/                    FastAPI bridge: /ask · /ask/stream (SSE) · /brief/export (PDF/Word) · /compare-cities · …
agent/retrieval.py      concept_qa + data_lookup (cited, offline, no engine)
eval/                   rubric.json (weighted criteria) + verifier.py (62 tests total)
scripts/gen_questions.py  regenerates QUESTIONS.md from the capability registry
app/dashboard.py        Streamlit UI (Ask · Explore · Visualize · Where's the AI · Governance)
data/                   coc_panel.csv (17 cities) · equity_*.csv · SOURCES.md
scripts/                fetch_acs.py (reproducible ACS pull from the Census API) · train_inflow.py · backtest.py
run_demo.py             end-to-end CLI entry point
```

## Scope & honesty

- **Real & calibrated (CA-600):** initial homeless counts (HUD PIT), per-person
  costs (Economic Roundtable), key flow rates + inflow (HUD SPM), the ACS→PIT
  learned model. Backtested against observed 2024.
- **Documented priors:** remaining transition rates (pending fuller HUD SPM fit),
  `at_risk`/`housed_stable` (ACS proxies), intervention effect sizes (the headline
  is reported as a band over ±50% of these).
- **Other 16 cities:** real PIT + ACS-driven inflow; flow rates & costs are CA-600
  priors (illustrative until locally calibrated).
- This tool **informs** a budget-timing tradeoff. It does **not** decide allocations
  or forecast individuals, surfaces equity at the population level only, and all
  outputs are ranges, not predictions.

## Deploy

Two ready-to-go paths (both run the Claude brain when `ANTHROPIC_API_KEY` is set, and fall
back silently to the deterministic rule planner otherwise):

- **Vercel** (full-stack: React static + FastAPI Python serverless, one URL) —
  [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md). Wired via `vercel.json` / `api/index.py`; needs the
  Pro plan for the Claude-live function timeout (or rule mode on Hobby).
- **Hugging Face Spaces** (single Docker container, FastAPI serves the app + API on
  port 7860) — [DEPLOY_HF.md](DEPLOY_HF.md). No function-timeout limit. The root
  `Dockerfile` builds it; set `ANTHROPIC_API_KEY` as a Space secret.
