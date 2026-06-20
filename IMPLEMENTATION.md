# WaitCost — Frontend Implementation Brief (design → real app)

**For the coding agent.** Build the real WaitCost web frontend from the finalized Claude Design
mockups, wired to the FastAPI backend that already exists in this repo. This file is the spec.
Read it top to bottom before writing code.

---

## 0. TL;DR

- **Build:** a React + Vite single-page app in a new `frontend/` folder.
- **Wire to:** the existing FastAPI backend (`api/main.py`) — already running on `:8000`, CORS is
  already open to Vite's `:5173`.
- **Match:** the mockups in `design/` pixel-for-pixel (tone, layout, type, color).
- **Golden rule:** every number on screen comes from the API. **Never hard-code or invent a
  figure.** The mocks contain placeholder numbers; the live engine is the only source of truth.
- **Apply the 5 fixes** in §6 — they are review findings, not in the mocks.

---

## 1. What this product is (so you make good calls)

WaitCost answers one question for U.S. city budget directors: *"If we delay funding homelessness
intervention, what will the delay cost us?"* — with real government data, honest uncertainty, an AI
that explains itself, and a hard rule that **a human, not the AI, makes the final allocation call.**

Mood: authoritative, humane, restrained — Our World in Data / USAFacts, **not** a flashy SaaS
dashboard, **not** alarmist. Data and uncertainty are first-class. Every number shows its source and
a range.

---

## 2. Where everything lives

```
design/                      ← the Claude Design export (READ THIS)
  project/WaitCost.html      ← the prototype entry point
  project/src/
    styles.css               ← design tokens + global styles  (copy tokens verbatim)
    components.css           ← per-screen component styles     (copy verbatim, then wire data)
    app.jsx                  ← shell: topbar, nav, city selector, routing/state
    ask.jsx                  ← Ask screen: thinking-stream, answer, declined, Tier-2 modal
    screens.jsx              ← Explore, Visualize, Model, Equity, Governance, Map
    charts-core.jsx          ← chart primitives (axes, bands, bars, dot-interval…)
    charts-more.jsx          ← the rest of the charts (18 total)
    data.js                  ← MOCK data the prototype renders from — read it to learn the
                               exact prop shapes each component expects, then replace with API
    tweaks-panel.jsx         ← design-exploration panel (mostly NOT shipped — see §6.4)
  project/screenshots/*.png  ← reference renders of every screen + state

api/main.py                  ← FastAPI routes (the contract you call) — see §4
api/payloads.py              ← exact response shapes (read this to know field names)
config/params.yaml           ← calibrated CA-600 assumptions
data/                        ← coc_panel.csv (17 cities), equity_*.csv
README.md                    ← project overview
```

**Strategy:** the design's `src/` is already React. Fork it as the starting point — copy `styles.css`,
`components.css`, and the component files into `frontend/src/`, then replace the `data.js` mock
imports with real API calls (§4). Match the *visual output* of the mocks; you may restructure
internals where it helps wire real data.

---

## 3. Stack & project layout

- **React + Vite** (JS or TS — TS preferred). Plain React; the mocks use no heavy UI kit.
- Charts: the mock chart components are hand-built SVG (`charts-core.jsx` / `charts-more.jsx`) and
  the backend returns **framework-agnostic chart specs** (`GET /chart`). Prefer rendering those SVG
  components from the specs. If you'd rather use a lib, Recharts/visx are acceptable **only if** the
  result still matches the mock styling and the data-viz palette in §5.
- No browser `localStorage` is required; keep app state in React.

```
frontend/
  index.html
  package.json
  vite.config.ts        ← proxy /api → http://localhost:8000  (or call :8000 directly; CORS is open)
  src/
    main.tsx
    App.tsx             ← shell + router + global { coc, theme } state
    api/client.ts       ← typed fetch wrappers for every endpoint in §4
    styles.css          ← from design/  (tokens)
    components.css       ← from design/
    components/…         ← Topbar, Nav, CitySelector, DisclaimerBar, StatTile, Pill, TierBadge, Modal…
    screens/             ← Ask, Explore, Visualize, Model, Equity, Governance, Map
    charts/              ← from design/  (charts-core, charts-more) wired to specs
```

**Run (two terminals):**
```bash
# backend
uvicorn api.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev      # http://localhost:5173
```

---

## 4. Backend contract (call these — do not change them)

All live in `api/main.py`; exact field names are in `api/payloads.py`. **Probe each once** (open
`http://localhost:8000/docs`) and build your types from the real response.

| Method & path | Use it for | Key params |
|---|---|---|
| `GET /health` | readiness | — |
| `GET /params` | data vintage, horizon, default budget, current coc | — |
| `GET /cocs` | the 17 cities for the City selector | — |
| `GET /tools` | Governance: agent capability/tool catalog + counts | — |
| `GET /context?coc=` | Map side-panel + city headline numbers | `coc` |
| `GET /equity?coc=` | Equity screen (disproportionality + unsheltered-by-group) | `coc` |
| `GET /charts` | Visualize: the 18-chart catalog (names, groups, descriptions) | — |
| `GET /chart?name=&coc=&budget_musd=&delay_years=` | one render-ready chart spec | `name`,`coc`,`budget_musd`,`delay_years` |
| `POST /scenario` | Explore: cost trajectory bands + cost-of-waiting | body below |
| `GET /effect-band?budget_musd=&delay_years=` | Explore sensitivity strip (±50% effects) | `budget_musd`,`delay_years` |
| `POST /ask` | Ask: full agent loop on a NL question | body below |
| `GET /model` | "Where's the AI": held-out R², SHAP, SPM cross-check | — |
| `GET /backtest` | "Where's the AI": predicted-2024 band vs observed dot | — |
| `GET /coc-points` | Map: 17 city bubbles (lat/lon, homelessness, housing cost) | — |
| `GET /geo` | Map: same points as a GeoJSON FeatureCollection | — |

**`POST /scenario` body:** `{ "budget_musd": 15, "delay_years": 3, "n_mc": 200, "mix": {…}|null, "coc": "CA-600" }`
→ returns:
```jsonc
{
  "budget_musd": 15, "delay_years": 3,
  "scenarios": [ { "scenario": "Status quo", "cum_cost_p50_musd": …, "cum_cost_p10_musd": …,
                   "cum_cost_p90_musd": …, "active_homeless": … }, {…act now…}, {…delay…} ],
  "bands": { "status_quo": { "year": [...], "p10": [...], "p50": [...], "p90": [...] },
             "act_now": {…}, "delay": {…} },          // values in $M
  "cost_of_waiting_musd": { "p50": …, "p10": …, "p90": … }
}
```

**`POST /ask` body:** `{ "question": "…", "approve_allocation": false, "coc": "CA-600" }`
→ returns the agent result. **Inspect it** (it carries the direct answer + range, the step/tool
trajectory with an Action Tier per step, the recommended chart name, the serif decision brief, and
— for out-of-scope or allocation questions — a declined flag or a Tier-2 gate). Drive the Ask UI
states (§5, screen 1) from these fields. For the Tier-2 flow, re-POST with `approve_allocation: true`
after the user checks the approval box. Read `agent/orchestrator.py` for the exact return dict.

---

## 5. Design tokens & screens

### Tokens (copy verbatim from `design/project/src/styles.css`)
- **Accent (civic indigo, "act now"):** `--accent #1A56DB`, `--accent-ink #143F9E`, `--accent-soft #E7EDFC`
- **Canvas / ink:** `--canvas #FAFAF7`, `--surface #FFF`, `--ink #1C1B16`, `--ink-2 #56534B`, `--ink-3 #807C72`
- **Data-viz trio (colorblind-safe, max 3 hues):** status-quo `--viz-neutral #8C877B` (warm gray) ·
  act-now `--viz-act` = accent · cost-of-waiting `--viz-wait #C2740C` (amber→clay, **never** fire-engine red),
  deep `--viz-wait-2 #B5532A`
- **Type:** UI = **Public Sans** (`--ui`); editorial/memo = **Source Serif 4** (`--serif`). Two weights.
  Use the serif for headlines and the decision brief — that's the "policy memo" gravitas.
- **Radii:** 8 / 10 / 14 / pill. Hairline borders, flat surfaces, generous whitespace, big tabular-num stats.
- **Dark mode:** full theme under `[data-theme="dark"]` (already defined). Toggle sets the attribute on `<html>`.

### App shell (persistent)
Topbar: "WaitCost · COST OF DOING NOTHING" mark · **City selector** (17 CoCs, **Los Angeles / CA-600
default**) · data-vintage chip ("HUD 2024 PIT · Census ACS 2024 (API)") · quiet **disclaimer bar**:
*"Informs a budget-timing tradeoff. Does not decide allocations or forecast individuals. All figures
are ranges."* Nav tabs: **Ask · Explore · Visualize · Where's the AI · Equity · Governance · Map.**
The selected `coc` is **global state** — changing it re-fetches and re-skins every screen.

### Screens (build in this order)
1. **Ask (hero).** One NL input + suggested-question chips + system-facts row ("17 CoC cities · 5 AI
   agents · 18 decision charts · runs fully offline"). On submit → **thinking-stream**: stream the
   trajectory steps from `/ask`, each with a **tier badge**, pausing at any Tier-2 step. Then reveal
   the **Direct Answer card** (headline number + 80% range + plain-English sentence), the
   **recommended chart** beneath it, a collapsible **Agent trajectory** (tool calls + tier), and the
   **decision brief** in the serif. Build the **declined** card (calm refusal: *"I work at the city
   level and don't profile individuals"* + in-scope suggestions) and the **Tier-2 approval modal**
   (explicit "I am the budget director… informs, does not execute" checkbox; Approve / Skip).
   → `POST /ask`.
2. **Explore.** Sliders: annual budget, years of delay, intervention mix (prevention / rapid-rehousing /
   supportive housing). Large **cost-trajectory fan chart** (status-quo / act-now / delay, each with a
   P10–P90 band, 10-yr x-axis). Three KPI cards. **Sensitivity strip** (headline as a range under ±50%
   of the low-confidence effects). → `POST /scenario` + `GET /effect-band`. Debounce slider calls.
3. **Visualize.** Left picker of the **18 charts**; selecting one renders it large with caption + source
   line. → `GET /charts` (catalog) + `GET /chart?name=` (spec). Reuse the chart components.
4. **Where's the AI.** Model card: metric tiles (held-out R², ML-vs-HUD-SPM cross-check, model type,
   backtest error), **SHAP horizontal bar** (housing cost on top), and a **backtest dot-interval**
   (predicted-2024 band with the observed dot inside). → `GET /model` + `GET /backtest`.
5. **Equity (the differentiator).** Serif headline ("Who bears this"), the **population-level-only**
   callout, a big lead stat, a **disproportionality** chart (bars past 1.0× highlighted in clay), and
   an **unsheltered-rate-by-group** chart with a citywide reference line. → `GET /equity?coc=`.
   Weighty and respectful; population-level only, never individual.
6. **Governance.** Action-Tiers table (Tier 0–1 automatic; Tier 2 human approval), an interactive
   **data-sufficiency demo** (toggle a thin-data condition → app *declines* rather than guessing),
   a data-sources list, a short lifecycle/recalibration note. → `GET /tools` (+ a declining `/ask`
   for the demo, or a static illustrative state).
7. **Map.** U.S. map, **17 city bubbles** sized by homelessness rate per 1,000; clicking a bubble sets
   the global `coc` (re-skinning every screen). Selected-city side panel with headline numbers.
   → `GET /coc-points` (or `/geo`) + `GET /context?coc=`.

### States to design for every data view
loading (skeleton shimmer — class `.skel` exists) · success · empty · **declined** (Ask) · error.

---

## 6. Review fixes — apply these (they are NOT in the mocks)

**6.1 Two-line text overlap (do not replicate).** In the exported screenshots, any pill / tier badge /
button / agent-step / footnote whose label wraps to a second line overlaps the line below it (e.g.
"Approve & continue", "Reset to baseline", "5 steps / 4 tool calls", agent-step titles, model-card
source lines). The CSS in `styles.css`/`components.css` looks correct (buttons/pills use padding, not
fixed heights), so this is **most likely a screenshot-rasterizer artifact** — but **verify in a real
browser**. If it reproduces: give pills/badges/buttons `line-height ≥ 1.2` and `min-height` (never a
fixed `height`) so they grow with content; add `white-space: nowrap` to labels meant to be one line
(tier badges, the facts row). The shipped app must have **zero overlapping text** at all viewports.

**6.2 Explore fan chart axis.** The mock's y-axis runs to ~$10B while the three lines sit at ~$4.5–5.5B,
so half the chart is empty and the scenarios are hard to tell apart. **Auto-fit the y-axis to the data
range** (with a little padding) and ensure status-quo / act-now / delay lines + bands are visually
distinct (the §5 palette + a legend). The separation between scenarios is the whole point of the screen.

**6.3 Number consistency = use the API.** The mocks show inconsistent placeholders ("$357M" on one
screen, "$346M" on another). **Render only live API values.** No hard-coded headline numbers anywhere.

**6.4 The Tweaks panel is not a product feature.** `tweaks-panel.jsx` (accent picker, density, font
picker, chart-palette) is a design-exploration tool. **Ship only the dark-mode toggle** as a real
control (in the topbar or a small settings menu). Drop the accent/density/font/palette pickers, or hide
them behind a dev-only flag.

**6.5 Map geography.** Use the real lat/lon from `GET /coc-points` (or `/geo`) on a proper U.S.
projection (e.g. d3-geo `geoAlbersUsa`, or a us-atlas TopoJSON) so bubbles sit in the right places —
not the stylized outline with approximate positions in the mock.

---

## 7. Accessibility (part of the pitch — non-negotiable)
WCAG 2.1 AA contrast; visible focus states (the `:focus-visible` ring is already in `styles.css`);
full keyboard nav for tabs, the city menu, and the Tier-2 modal (focus-trap + Esc); charts legible
**without color alone** (direct labels / shapes / patterns, not hue-only encoding); honor
`prefers-reduced-motion` (already handled in CSS — keep it). Run an axe/Lighthouse pass before "done".

---

## 8. Definition of done
- All 7 screens + the Ask states (thinking-stream, answer, declined, Tier-2 modal) + light **and** dark
  mode, responsive down to tablet.
- City selector changes `coc` and re-skins **every** screen; LA/CA-600 is the default.
- Every figure on screen traces to an API response; nothing hard-coded; no individual- or
  neighborhood-level data anywhere.
- The five §6 fixes are applied; **no overlapping text** anywhere; Explore axis fits the data.
- The Tier-2 gate actually blocks an allocation answer until the box is checked; the declined state
  renders for out-of-scope questions.
- `npm run build` succeeds; axe/Lighthouse AA clean on the main screens.

## 9. Don'ts
Don't invent numbers · don't change backend values · don't add individual/neighborhood data · no
alarmist red · don't ship the Tweaks panel · don't drop the disclaimer bar, the source lines, or the
uncertainty ranges (they're the credibility of the product).
