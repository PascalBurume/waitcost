# WaitCost — Data Sources Manifest

Every data source used anywhere in this project, in one place. All data is **real public data** — nothing
is synthetic. Compiled 2026-06-16.

```
data_sources/
  SOURCES_MANIFEST.md        ← this file (master index)
  datasets/                  ← the actual data the model + equity lens run on
    coc_panel.csv            17 CoCs × real PIT counts + ACS economic features
    equity_race.csv          17 CoCs × 7 race groups: total & unsheltered homeless (HUD race tables)
    equity_pop_shares.csv    17 CoCs × 7 race groups: population shares (Census ACS)
  calibration/
    params.yaml              CA-600 calibrated assumptions; each value tagged source: + confidence:
  model_artifact/
    inflow_model.json        the trained inflow model (metrics + SHAP + calibration), output of training
  source_registry/
    SOURCES.md               full audit trail for the calibration panel (field-by-field provenance)
    CITY_SOURCES.md          per-city situation + care/strategy plan index (readable)
    city_sources.json        same, machine-readable (the CityBriefAgent grounds on this)
```

---

## 1. Primary data sources (drive the model + the numbers)

| # | Source | Publisher | Vintage | Used for | Link |
|---|---|---|---|---|---|
| 1 | **Point-in-Time (PIT) Homeless Counts** — CoC Populations & Subpopulations reports | HUD | 2024 (counted Jan 2024; pub. Dec 2024) | `pit_total/sheltered/unsheltered/chronic` in `coc_panel.csv`; model target; backtest observed | https://www.hudexchange.info/programs/coc/coc-housing-inventory-count-reports/ |
| 2 | **American Community Survey (ACS) 1-year estimates** (Census API; reproducible via `scripts/fetch_acs.py`, verified 0/119 ≥5%) | U.S. Census Bureau | 2024 | model features: `population, median_home_value, median_household_income, poverty_rate, pop_density…` | https://api.census.gov/data/2024/acs/acs1 |
| 3 | **HUD System Performance Measures (SPM)** — CoC Performance Profile, CA-600 | HUD | FY2023 | calibrates transition rates + monthly inflow (M1, M2, M5, M7) in `params.yaml` | https://files.hudexchange.info/reports/published/CoC_Perf_CoC_CA-600-2023_CA_2023.pdf |
| 4 | **HUD race/ethnicity subpopulation tables (PIT)** | HUD | 2024 | `equity_race.csv` (total & unsheltered by group) | https://www.hudexchange.info/programs/coc/coc-housing-inventory-count-reports/ |
| 5 | **Per-person cost anchors** — Los Angeles homelessness cost studies (e.g. Economic Roundtable "Where We Sleep") | Economic Roundtable / LA studies | 2024$ | per-state monthly cost anchors in `params.yaml` (see inline `source:` tags) | https://economicrt.org/publication/where-we-sleep/ |

Full field-by-field provenance, geographic-matching caveat, and the NYC right-to-shelter outlier note are in
`source_registry/SOURCES.md`.

## 2. Strategy / care-plan sources (per city — for the CityBriefAgent)

Lead agency + current strategic/care plan for each of the 17 CoCs, with situation notes and citations, are in
`source_registry/CITY_SOURCES.md` (readable) and `source_registry/city_sources.json` (machine-readable). National
framing:

- **All In: The Federal Strategic Plan to Prevent and End Homelessness** (USICH) — https://www.usich.gov/federal-strategic-plan/overview
- **HUD Continuum of Care (CoC) Program** — https://www.hud.gov/program_offices/comm_planning/coc

The 17 city plans (LAHSA, KCRHA Five-Year Plan, Home by the Bay, Homeward DC 2.0, San Diego RTFH action plan,
Chicago Plan 2.0 / 2026–31 Blueprint, Philadelphia Roadmap to Homes, Miami-Dade Priority Home, etc.) are listed
with links in the registry files. Four links are flagged `"verify": true` (Portland, NYC, Knoxville, Philadelphia)
— the plans are real; reconfirm the canonical URL before the demo.

## 3. How the sources flow through the project

```
HUD PIT + Census ACS  ──►  datasets/coc_panel.csv  ──►  model training (Ridge / GB-stumps + SHAP, leave-one-CoC-out CV)
                                                          └─► model_artifact/inflow_model.json
HUD SPM (CA-600)      ──►  calibration/params.yaml  ──►  system-dynamics simulator + Monte Carlo + backtest
HUD race tables + ACS ──►  datasets/equity_*.csv    ──►  equity / disproportionality lens
per-city plans (web)  ──►  source_registry/*         ──►  CityBriefAgent (general city situation + strategy)
```

Reproduce the model + the web-app charts from these files with `notebooks/WaitCost_model_and_visuals.ipynb`.

## 4. Honesty notes
- Real & calibrated for **CA-600 (Los Angeles)**; the same trained model scores the other 16 cities, but their
  flow rates/costs use CA-600 priors (illustrative until locally calibrated). See `source_registry/SOURCES.md`.
- All outputs are **ranges**, not point predictions. The tool informs a budget-timing tradeoff; it does not decide
  allocations or forecast individuals.
