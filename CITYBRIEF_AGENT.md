# WaitCost — CityBriefAgent (third agent) spec

> **Status: shipped — and since superseded by a 4-agent roster.** This spec describes
> adding the *third* agent. A **fourth agent** (the **decision agent**, `agent/decision.py`)
> was added afterward. The current, canonical count comes from the code registry
> (`agent/tools.py` → `/tools`): **4 agents · 16 capabilities · 16 skills · 18 charts**
> (agents: analyst · visualization · city_brief · decision). Treat any "3 agents" / "2 AI
> agents" reference below as historical — see `ARCHITECTURE.md` for the current architecture.

**For the coding agent.** Add a third agent that answers **general questions about each city's
homelessness situation and its care plans / response strategy**, grounded in a curated source registry
(with citations) and — optionally — live web search. This complements the two existing agents (the
**analyst** orchestrator and the **visualization** agent); it does **not** touch the cost simulator's math.

---

## 0. Why this agent exists (and what it is NOT)
- The analyst agent answers *quantitative budget-timing* questions from the calibrated simulator.
- **CityBriefAgent answers qualitative/contextual questions:** "What's the homelessness situation in
  Seattle?", "What is San Diego's plan?", "Who leads the CoC in Chicago and what's their strategy?"
- It is a **grounded briefing agent**, not a freewheeling chatbot. Every answer is built from cited
  sources (the registry below, the project's own data, and — if enabled — live web results). It must
  **never invent** a figure, a plan name, or a strategy, and it labels its output clearly as
  **"general context — not the calibrated cost model"** so judges never confuse it with the simulator.

---

## 1. The grounding corpus (already in the repo — I built it)
- **`data/city_sources.json`** — for each of the 17 CoCs: `coc, city, coc_name, lead_agency,
  plan_title, plan_url, key_sources[], situation_note, verify`. Plus `national_frameworks`
  (USICH "All In", HUD CoC program). Sources were gathered by live web search on 2026-06-16.
- **`data/CITY_SOURCES.md`** — human-readable index of the same.
- Items with `"verify": true` (Portland, NYC, Knoxville, Philadelphia) should be re-confirmed before
  the demo; the named plan is real, but the canonical link may have moved.
- **Reuse existing project data too:** `agent/skills.retrieve_us_context(coc)` (counts, housing,
  poverty) and `analysis.equity.headline(coc)` already give quantitative context per city. The
  CityBriefAgent should weave those in so a brief has both *numbers* (from the engine) and *narrative +
  strategy* (from the registry).

---

## 2. Architecture — how it coordinates with the other two agents
- New module **`agent/city_brief.py`** with a `CityBriefAgent` class. Keep the same conventions as
  `agent/orchestrator.py`: record a `trajectory` of `{skill, tier, approved}`, log to `MEMORY.md`,
  decline out-of-scope.
- **Routing:** extend `agent/planner.py`:
  - Add two intents to `INTENTS`: **`city_situation`** and **`care_plan`** (strategy/plan questions).
    (`city_context` already exists for the quantitative snapshot — keep it; `city_situation` is the
    richer narrative brief, `care_plan` is specifically about the plan/strategy.)
  - Extend `classify_intent` regexes: `care_plan` ← "plan", "strategy", "what are they doing",
    "response", "approach", "initiative"; `city_situation` ← "situation", "what's happening",
    "how bad", "tell me about", "overview" (when not purely numeric).
  - In `WaitCostAgent` (orchestrator), when intent ∈ {`city_situation`, `care_plan`}, **delegate to
    `CityBriefAgent`** instead of running the simulator. This keeps a single front door (`/ask`) while
    the new agent handles the contextual branch — show the hand-off in the trajectory ("Routing to
    City Brief agent").
- **Action Tier:** all retrieval here is **Tier 0 (read-only)**. Live web fetch is also Tier 0 but
  gated by an explicit online flag (§4). Individual-/neighborhood-level questions → decline, exactly
  like the analyst (reuse the `out_of_scope` rule).

---

## 3. What a city brief contains (the output contract)
`CityBriefAgent.brief(coc, question=None)` returns a dict:
```jsonc
{
  "coc": "WA-500", "city": "Seattle",
  "lead_agency": "King County Regional Homelessness Authority (KCRHA)",
  "plan": { "title": "...", "url": "...", "summary": "<grounded, from situation_note + plan>" },
  "situation": "<narrative woven from retrieve_us_context() numbers + registry situation_note>",
  "indicators": { ...from retrieve_us_context()... },     // numbers come ONLY from the engine
  "national_context": "All In (USICH) framing this aligns to",
  "sources": [ {"title": "...", "url": "..."} , ... ],     // every source actually used
  "label": "General context — not the calibrated cost model.",
  "online": false,                                          // true if live search augmented it
  "trajectory": [ ... ]
}
```
- **Narration:** when Gemma is available (see `FINALIZE.md`), use it to write `situation`/`plan.summary`
  from the structured facts, with the **same number-guard**: the LLM may phrase, but every figure must
  trace to `retrieve_us_context()`/`city_sources.json`; otherwise fall back to a deterministic template.
- Always attach `sources` and the `label`.

---

## 4. Offline-first, with optional live search (preserve the "fully offline" pitch)
- **Default = fully offline.** Answer from `city_sources.json` + project data. No network. This keeps
  the project's core claim intact and makes the demo reproducible.
- **Optional live mode**, behind an explicit flag **`WAITCOST_ONLINE=1`**: the agent may call a search/
  fetch tool to refresh or deepen a brief (e.g. pull the latest from the plan URL). Implement it behind
  a small `agent/web_search.py` interface with a no-op default, so it works whether or not a search
  backend (an MCP search tool, or a simple `requests`-based fetch the user runs locally) is wired in.
  When used, **every** live fact must carry its URL in `sources`, and set `"online": true`.
- Never let live mode become a hard dependency; if it's off or fails, return the offline brief.

---

## 5. API + frontend
- **API** (`api/main.py` + `api/payloads.py`):
  - `GET /city-brief?coc=CA-600` → `CityBriefAgent.brief(coc)`.
  - `GET /city-sources?coc=CA-600` → raw registry entry from `city_sources.json`.
  - Free-form general questions already flow through `POST /ask` (the orchestrator routes
    `city_situation`/`care_plan` to this agent).
- **Frontend** (the React app from `IMPLEMENTATION.md`): add a **"City Brief"** panel — simplest as a
  section on the **Map** screen's city side-panel, or a small new tab. Show: lead agency, plan title
  (linked), the situation narrative, the indicator tiles, and a **Sources** list with clickable links.
  Badge the whole panel **"General context — not the calibrated model."** Render an "online/offline"
  chip so it's clear when live search was used.

---

## 6. Tool registry + counts (keep the system honest)
- Register the new agent + its capability in `agent/tools.py` so `registry_summary()` reflects it.
- **Keep every agent/chart count in sync with the registry** (`agent/tools.py` → `/tools`). After the
  decision agent landed the canonical figure is **4 agents · 16 capabilities · 16 skills · 18 charts**
  (was bumped 2 → 3 here, then 3 → 4). When a count changes, grep the docs for the old number
  (`README.md`, `ARCHITECTURE.md`, `IMPLEMENTATION.md`, `DESIGN_PROMPT.md`, the Streamlit app, the design
  copy) and update all of them — the registry is the single source of truth.

---

## 7. Tests (extend `eval/verifier.py`, keep it green)
- Registry loads and every one of the 17 CoCs has a `lead_agency`, `plan_title`, and ≥1 `key_source`.
- `CityBriefAgent.brief(coc)` for a few CoCs returns a non-empty `situation`, a `plan.url`, and a
  non-empty `sources` list; the `label` is present.
- A `care_plan`/`city_situation` question routed through `/ask` lands on the CityBriefAgent.
- An individual-level question ("which family will become homeless in Chicago?") is **declined**.
- Offline mode works with no network; with `WAITCOST_ONLINE=1` and the search interface stubbed, the
  brief still returns and `online` reflects whether live data was used.
- **Number-guard test:** if Gemma narration introduces a figure not in the facts, the deterministic
  template is used instead.

---

## 8. Definition of done
The agents coordinate cleanly (analyst → simulator; viz → charts; **city-brief → grounded context**;
decision → recommendation — the roster is now **4 agents**, see the status banner above);
`/city-brief` and `/city-sources` work for all 17 CoCs and every answer cites real sources; the panel
renders with the "general context" label and clickable sources; offline by default, live search is an
opt-in that never breaks the demo; counts updated everywhere to match the registry; `pytest eval/verifier.py` green.

## 9. Don'ts
Don't let this agent emit any number not from the engine/registry · don't drop citations · don't profile
individuals or sub-city geographies · don't make live web search a hard dependency (offline must work) ·
don't blur the line between this contextual brief and the calibrated cost model — always label it.
