# Data Methodology — where the data comes from & how WaitCost uses it

This document explains, for the WaitCost project, **(a) the online sources every data point comes from**,
**(b) how we collected it**, and **(c) how each source is used** in the model, the simulator, the equity
lens, and the agents.

**Three principles**
- **All real, all public.** Nothing in the project is synthetic. Every figure traces to a named
  government or research source with a vintage.
- **Collected once, runs offline.** The data is small, static, annual public data, so we curate it once
  (with provenance) into files in the repo — the app does **not** scrape the web at runtime.
- **Ranges, not false precision.** Outputs are uncertainty bands; the tool informs a budget-timing
  tradeoff, it does not decide allocations or forecast individuals.

---

## 1. The sources (origin → how collected → how used)

### 1.1 HUD Point-in-Time (PIT) homeless counts — *the model's target & the backtest*
- **Origin:** U.S. Department of Housing & Urban Development (HUD), 2024 Continuum-of-Care (CoC)
  **Homeless Populations & Subpopulations** reports (counted Jan 2024; published Dec 2024).
- **Online source:**
  - Index of all CoC reports: <https://www.hudexchange.info/programs/coc/coc-homeless-populations-and-subpopulations-reports/>
  - PIT/HIC data hub: <https://www.hudexchange.info/programs/hdx/pit-hic/>
  - Per-CoC PDF pattern: `https://files.hudexchange.info/reports/published/CoC_PopSub_CoC_<CoC>-2024_<ST>_2024.pdf`
    (e.g. Los Angeles: `…/CoC_PopSub_CoC_CA-600-2024_CA_2024.pdf`)
  - National report context (AHAR): <https://www.huduser.gov/portal/datasets/ahar.html>
- **How collected:** for each of the 17 CoCs we opened the published PDF, read the Population &
  Subpopulation table, and transcribed four fields — `pit_total`, `pit_sheltered`, `pit_unsheltered`,
  `pit_chronic` — into `datasets/coc_panel.csv`. A subset of cities was spot-checked against the live
  HUD figure to confirm no transcription error.
- **How used:** `pit_total / population × 1000` is the **model's training target** (homelessness rate per
  1,000). The counts also seed the **backtest** (real 2023 → predict 2024) and feed the city headline
  numbers in the app.

### 1.2 U.S. Census ACS 2024 1-year estimates — *the model's input features*
- **Origin:** U.S. Census Bureau, American Community Survey (ACS) 2024 1-year estimates (released
  Sept 2025).
- **Online source:**
  - Official platform: <https://data.census.gov>
  - Release notes: <https://www.census.gov/programs-surveys/acs/news/data-releases/2024/release.html>
  - Access layer we used (faithful republisher, readable HTML profiles): <https://censusreporter.org/>
- **How collected:** now pulled **directly from the Census API** (reproducibly) via
  `scripts/fetch_acs.py` — it fetches `population`, `per_capita_income`, `median_household_income`,
  `poverty_rate` (B17001_002E ÷ B17001_001E), `median_home_value`, `persons_per_household` per
  county/place by FIPS, and joins Census Gazetteer land area for `pop_density_sqmi`. The original values
  were first transcribed from **Census Reporter** (a faithful republisher of the same Census data);
  re-running against the live API **verified them exactly** — 0 of 119 values differed by ≥5% (only
  sub-0.1% rounding in two density figures). `coc_panel.csv` now carries `acs_release = "ACS 2024 1-yr (API)"`.
- **How used:** four of these become the **learned model's features** —
  `log_median_home_value`, `poverty_rate`, `median_household_income`, `log_pop_density` — predicting the
  homelessness rate. `population` converts the predicted rate into people and the monthly inflow.

### 1.3 HUD System Performance Measures (SPM) FY2023 — *the simulator's flow rates (CA-600)*
- **Origin:** HUD CoC Performance Profile, CA-600 Los Angeles, FY2023 (HMIS-reported).
- **Online source:** <https://files.hudexchange.info/reports/published/CoC_Perf_CoC_CA-600-2023_CA_2023.pdf>
- **How collected:** read four measures from the PDF and converted annual rates to monthly transition
  hazards (formulas in `source_registry/SOURCES.md`): **M5** first-time homeless → monthly inflow,
  **M7** exit-to-permanent-housing, **M1** length of time homeless, **M2** returns within 6 months.
- **How used:** calibrates the system-dynamics simulator's **transition rates and inflow** in
  `calibration/params.yaml`. M5 (≈2,485/mo) also independently **cross-checks** the ML-predicted inflow
  (~2,817/mo), agreeing within ~13%.

### 1.4 Per-person cost studies — *the dollar anchors*
- **Origin:** Economic Roundtable and related Los Angeles cost research (2024 dollars).
- **Online source:** <https://economicrt.org/publication/where-we-sleep/>
- **How collected:** read published per-person public-cost figures by housing status; each value is
  tagged inline with `source:` and `confidence:` in `calibration/params.yaml`.
- **How used:** the **cost layer** of the simulator — converts people-in-each-state-over-time into the
  10-year public cost trajectories and the headline "cost of waiting".

### 1.5 HUD race/ethnicity subpopulation tables + ACS race shares — *the equity lens*
- **Origin:** HUD 2024 PIT race/ethnicity subpopulation tables; Census ACS race population shares.
- **Online source:** same HUD CoC reports index (1.1) and Census/Census Reporter (1.2).
- **How collected:** transcribed total & unsheltered homeless counts by 7 race groups into
  `datasets/equity_race.csv`, and population shares into `datasets/equity_pop_shares.csv`, for all 17 CoCs.
- **How used:** the **equity / disproportionality** analysis (over-representation vs. population share,
  unsheltered-rate by group) — **population-level only, never individual-level.**

### 1.6 Per-city strategic / care plans — *the CityBrief agent's grounding corpus*
- **Origin:** each CoC's lead agency (LAHSA, KCRHA, SF HSH, DC ICH, Miami-Dade Homeless Trust, etc.) and
  the federal USICH "All In" plan.
- **Online source:** all links are in `source_registry/city_sources.json` and `CITY_SOURCES.md`
  (national framing: <https://www.usich.gov/federal-strategic-plan/overview>).
- **How collected:** gathered by **live web search** during the build, recording lead agency + current
  plan title + authoritative URL + a sourced situation note per city.
- **How used:** the **CityBrief agent** answers general "what's the situation / what's the plan?"
  questions, grounded in this corpus with citations (labeled "general context — not the calibrated
  cost model").

---

## 2. How the data flows through the project

```
HUD PIT + Census ACS  ─► datasets/coc_panel.csv ─► model training (Ridge/GB-stumps + SHAP, leave-one-CoC-out CV)
                                                    └─► model_artifact/inflow_model.json
HUD SPM (CA-600)      ─► calibration/params.yaml ─► system-dynamics simulator + Monte Carlo + backtest
Cost studies          ─► calibration/params.yaml ─► cost layer (10-yr public cost, cost-of-waiting)
HUD race + ACS        ─► datasets/equity_*.csv    ─► equity / disproportionality lens
Per-city plans (web)  ─► source_registry/*        ─► CityBrief agent (situation + strategy, cited)
```

**In code:**
- **Ingest** — `model/inflow_model.py:load_panel()` reads `coc_panel.csv`, derives the rate, log-transforms skewed features.
- **Transform** — `_design()` selects the 4 features and z-score standardizes them.
- **Train + select** — `select_model()` grid-searches Ridge/GB-stumps, scored by `leave_one_out()` (held-out CV).
- **Explain / calibrate** — `shap_values()` (exact SHAP) and `calibrate_inflow()` (rate → monthly inflow + band).
- **Serve** — saved to `model/inflow_model.json`; the simulator (`model/simulate.py`, `montecarlo.py`) and the
  FastAPI endpoints (`/scenario`, `/ask`, `/model`, `/backtest`, `/equity`, `/chart`) consume it.

---

## 3. Honesty & limitations (disclosed)
- **Calibrated for CA-600 (Los Angeles).** The same trained model scores the other 16 cities, but their
  flow rates and costs use CA-600 priors (illustrative until locally calibrated).
- **Geographic matching:** CoC boundaries ≈ a single county/principal place; multi-county CoCs were
  excluded from the model panel to keep the per-capita rate clean (see `SOURCES.md`).
- **Structural outlier:** NY-600 (right-to-shelter) is ~97% sheltered; the model under-predicts it, which
  we surface as a residual rather than hide.
- **Collection layer:** HUD PIT comes from HUD's published PDFs (read & transcribed). The ACS economic
  features are now pulled **directly from the Census API** and are reproducible via `scripts/fetch_acs.py`;
  re-running it verified the original Census Reporter transcription exactly (0 of 119 values differed by
  ≥5%). Census Reporter republishes the same Census Bureau data, so it remains a valid cross-check.

*Full per-field audit trail: `source_registry/SOURCES.md`. Per-city plan links: `source_registry/city_sources.json`.*
