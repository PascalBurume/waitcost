# WaitCost — Frontend

React + Vite + TypeScript single-page app for WaitCost, wired live to the FastAPI
engine in `../api`. Every number on screen comes from the API — nothing is
hard-coded (the golden rule from the implementation brief).

## Run (two terminals)

```bash
# 1) backend (from the repo root, one level up)
uvicorn api.main:app --reload --port 8000

# 2) frontend
cd frontend
npm install
npm run dev          # http://localhost:5173
```

`vite.config.ts` proxies `/api/*` → `http://localhost:8000`, so the app talks to
the engine through its own origin (CORS is also open on the backend if you'd
rather point `API_BASE` straight at `:8000`).

```bash
npm run build        # tsc -b && vite build  → dist/
```

## Structure

```
src/
  api/         client.ts (typed fetch for every route) + types.ts
  charts/      ChartView.tsx (one renderer per backend chart `kind`), USMap.tsx
               (geoAlbersUsa + us-atlas), primitives.tsx (axes/scales/tooltip)
  components/  Shell.tsx (topbar, city selector, nav), ui.tsx (modal, stat tiles…)
  screens/     Ask, Explore, Visualize, Model, Equity, Governance, MapScreen
  state.tsx    global { coc, theme, params, cocs } — changing coc re-skins everything
  styles.css / components.css   copied verbatim from the design export
```

## Notes on the review fixes (brief §6)

- **§6.1 no overlapping text** — pills/badges/buttons grow with content; one-line
  labels (tier badges, facts row) use `white-space: nowrap`. Verified in-browser.
- **§6.2 Explore axis** — the fan chart and `line_band` charts auto-fit the y-axis
  to the data (P10–P90) so the three scenarios + bands stay distinguishable.
- **§6.3 number consistency** — every figure is rendered from a live API response.
  The Explore intervention mix uses the engine's canonical keys
  (`prevention` / `rapid_rehousing` / `permanent_supportive_housing`) so the
  cost-of-waiting KPI agrees with the sensitivity baseline.
- **§6.4 Tweaks panel dropped** — only the dark-mode toggle ships (top bar).
- **§6.5 real map** — `geoAlbersUsa` + us-atlas TopoJSON; bubbles sit at true
  lat/lon from `/coc-points`.

The chart specs returned by `/chart` carry their own hex colors (including a red
that the brand forbids); `vizColor()` remaps every series to the colorblind-safe
design trio by role, so no banned red is ever drawn.

## Tier-2 gate

The backend has no "needs approval" flag, so the binding-allocation gate is
enforced client-side (`Ask.tsx`): an allocation request opens the approval modal
and the answer is withheld until the responsibility box is checked, at which
point the question is re-POSTed with `approve_allocation: true` and the
`optimize_allocation` Tier-2 step appears (approved) in the trajectory.
Out-of-scope (individual / sub-CoC) questions return `{declined: true}` and render
the refusal card.
