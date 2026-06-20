# WaitCost — Enhancements spec (3 features)

**For the coding agent.** Add three features that strengthen the rubric where it counts (Responsible AI,
AI Reasoning) without changing any of the engine's numbers. Build in the order below — ① and ② are
low-risk and lean on what already exists; ③ is the bigger change.

## Non-negotiable rules (same as the rest of the project)
- **Stay fully offline.** No new network calls. No new heavy deps.
- **The engine owns every number.** These features *display* or *route* — they never compute or alter a figure.
- **Don't break existing endpoints or the frontend contract.** Add, don't rewrite.
- **Keep `pytest eval/verifier.py` green** and add tests for each feature.
- **Accessibility:** anything interactive is keyboard-focusable with an aria label (this is part of the pitch).

---

## ① Provenance on every number  (Responsible AI · trust)
**Goal:** a user can click/focus any figure on screen and see *where it came from* + its vintage + "this is a
range, not a point." This is the single clearest "we're not a chatbot that makes up numbers" signal.

**Backend**
- Add `api/payloads.py: provenance_payload()` and route `GET /provenance` in `api/main.py`. It returns a small
  map keyed by **metric family**, each with `{label, source, vintage, note}`, e.g.:
  - `homeless_counts` → HUD 2024 PIT (CoC PopSub), counted Jan 2024
  - `economic_features` → U.S. Census ACS 2024 1-yr (Census API, reproducible via `scripts/fetch_acs.py`, verified 0/119 ≥5%)
  - `flow_rates` → HUD SPM FY2023 (CA-600)
  - `costs` → Economic Roundtable "Where We Sleep" (2024$)
  - `cost_of_waiting` / `scenario` → "Engine output — 80% Monte-Carlo range; not a point estimate"
  - `equity` → HUD race tables + ACS shares (population-level only)
  Source the text from `data_sources/SOURCES_MANIFEST.md` (don't hard-code new facts).
- Chart specs already carry a `source` string (`analysis/viz.build_chart`) — reuse it; don't duplicate.

**Frontend** (`frontend/src`)
- Add a `<Provenance metric="cost_of_waiting">…</Provenance>` wrapper in `components/ui.tsx`: wraps a stat/number,
  shows a small popover on click **and** keyboard focus (button with `aria-describedby`), pulling text from a
  `/provenance` map fetched once into `state.tsx`.
- Apply it to: the **Direct Answer** headline + range (Ask), the KPI/StatTiles (Explore, Map panel), the model-card
  tiles (Model), and the equity stats (Equity). Chart captions already show a source line — make that line a
  focusable popover too (same component).
- Visual: a tiny "ⓘ" affixed to the number; popover is flat, hairline border, matches the design tokens.

**Test:** `GET /provenance` returns an entry for each metric family with non-empty `source` + `vintage`.

---

## ② Agent self-evaluation scorecard  (Responsible AI · credibility)
**Goal:** surface that the agent is *tested* — almost no hackathon team shows this. Put a "How we tested this
agent" panel on the **Governance** screen.

**Backend**
- Add `api/payloads.py: eval_payload()` and route `GET /eval`. It computes/loads, fast and offline:
  - **routing accuracy** — run `classify_intent` (agent/planner.py) over the cases in `eval/routing_cases.py`
    (reuse `eval/routing_benchmark.py` if it already returns a score) → `{accuracy, n_cases}`.
  - **guardrail refusals** — count of out-of-scope / individual-level prompts the agent correctly declines
    (use the out-of-scope cases in `routing_cases.py`, or add ~6 red-team prompts there) → `{refused, total}`.
  - **deterministic checks** — the verifier count. Don't run pytest live; read a cached number from a small
    generated file (e.g. `eval/last_run.json`, written by a one-line make/script) or hard-read the known total,
    and label it "39/39 deterministic checks".
  - **registry** — include `agent/tools.registry_summary()` (5 agents · 16 capabilities · 16 skills · 18 charts) for context.
- Keep it well under ~1s; if routing over all cases is slow, cache to `eval/eval_summary.json` and serve that.

**Frontend**
- On **Governance**, add a "How we tested this agent" card: stat tiles for routing accuracy %, guardrail
  refusals (e.g. "8/8 unsafe prompts refused"), and "39/39 checks", plus a short list of 3–4 example refused
  prompts (from `/eval`). Label it clearly; link to `eval/` in the repo note.

**Test:** `GET /eval` returns `routing_accuracy` in [0,1], `guardrail.refused == guardrail.total`, and the
registry counts; assert it doesn't shell out to pytest.

---

## ③ Multi-turn follow-ups on Ask  (AI Reasoning · feels real)
**Goal:** follow-up questions keep context, so a director can say *"now try 5 years"* or *"what about Chicago?"*
and the agent inherits the city/budget/delay it doesn't restate. **Stateless on the server** (client passes the
prior context) to stay offline + reproducible.

**Backend**
- `api/main.py` `AskRequest` (and the `/ask/stream` body) gains optional `context: {coc, budget_musd,
  delay_years, last_intent} | null`.
- `agent/planner.py`: add **slot inheritance** — if `plan()` extracts a missing `budget_musd` / `delay_years` /
  `coc`, fill it from `context`. Detect follow-ups ("now", "instead", "what about", "and", "try") to bias toward
  inheriting. New city named in a follow-up overrides the prior `coc`.
- `agent/orchestrator.py`: `answer(question, ..., prior=None)` merges `prior` into the plan before running. The
  return already includes the resolved `plan` (coc/budget/delay) — the client reads it to update its context.
- Keep every existing guardrail per turn (out-of-scope still declines; Tier-2 still gates). Cap any history at a
  few turns.

**Frontend**
- `state.tsx`: hold a `conversation` = the last resolved `{coc, budget, delay, intent}` + a short transcript.
- `screens/Ask.tsx`: send the current `context` with each question; render answers as a **thread** (one answer
  card per turn, newest on top or bottom); after each response, update `context` from `result.plan`. A "New
  conversation" button clears it.

**Test:** two-call sequence — Q1 `"$15M, wait 3 years, Los Angeles"`, Q2 `"now 5 years"` with the returned
context → resolves `budget=15`, `coc=CA-600`, `delay=5`. Assert inheritance + that a fresh question with no
context still works.

---

## Definition of done
- `/provenance` and `/eval` return real data; the Ask flow carries context across turns.
- Provenance popovers appear on the headline, KPIs, model tiles, equity stats, and chart sources — keyboard
  accessible. Governance shows the self-eval card. Ask supports follow-ups.
- No engine numbers changed; `pytest eval/verifier.py` green; new tests added; offline preserved.
- Bump any counts/docs only if a count actually changes (these features add 2 endpoints, not agents/charts).
