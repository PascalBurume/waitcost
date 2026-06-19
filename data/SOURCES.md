# Data sources — WaitCost calibration panel

All values are real public data. Nothing in `coc_panel.csv` is synthetic. Each
column is traceable to the source below, with vintage. This file is the audit
trail for the learned inflow model and the CA-600 calibration in
`config/params.yaml`.

## Target: Point-in-Time (PIT) homeless counts
- **Source:** U.S. Dept. of Housing & Urban Development (HUD), 2024 Continuum of
  Care (CoC) Homeless Populations & Subpopulations reports (per-CoC PDFs).
- **Vintage:** 2024 PIT counts, conducted January 2024; published Dec 9, 2024.
- **URL pattern:** https://files.hudexchange.info/reports/published/CoC_PopSub_CoC_<CoC>-2024_<ST>_2024.pdf
- **Fields used:** `pit_total` = Total Homeless Persons; `pit_sheltered` =
  Emergency Shelter + Transitional Housing; `pit_unsheltered` = Unsheltered;
  `pit_chronic` = Total Chronically Homeless Persons.
- **Example (CA-600 Los Angeles, PIT 1/24/2024):** total 71,201;
  sheltered 21,692 (ES 19,540 + TH 2,152); unsheltered 49,509; chronic 29,823.

## Features: economic / housing conditions (American Community Survey)
- **Source:** U.S. Census Bureau, American Community Survey (ACS) 2024 1-year
  estimates, pulled directly from the official Census API and **reproducible**
  via `scripts/fetch_acs.py`. The original values were first transcribed from
  Census Reporter (a faithful republisher of the same Census data); re-fetching
  from the live API **verified them** — 0 of 119 values differed by ≥5%. The
  panel carries `acs_release = "ACS 2024 1-yr (API)"`.
- **Geographic unit:** the principal county (or, for NYC/Chicago, the principal
  place) of each CoC. See "geographic matching" caveat below.
- **Fields:** `population`, `per_capita_income`, `median_household_income`,
  `poverty_rate` (% persons below poverty), `median_home_value` (median value of
  owner-occupied units, the housing-cost signal), `persons_per_household`,
  `pop_density_sqmi`.

## Derived
- `homeless_rate_per_1k` = `pit_total` / `population` × 1000  (computed in
  `model/inflow_model.py`; not stored, to keep the CSV to source values only).

## Panel growth (adding cities)
The model panel started at 15 CoCs and is extensible. Added 2026-06-15: CA-503
(Sacramento City & County / Sacramento County) and AZ-501 (Tucson/Pima County /
Pima County) — both single-county CoCs, PIT from the 2024 HUD PopSub reports, ACS
from the Census API (`scripts/fetch_acs.py`). To add a city: append its real PIT + ACS row to
`coc_panel.csv` (single-county CoCs only, to keep the per-capita rate clean) and
re-run `scripts/train_inflow.py`. The same model then scores it.

## Geographic matching caveat (a known limitation, disclosed)
CoC boundaries are not identical to county/place boundaries. We restrict the
panel to CoCs whose service area is well-approximated by a single county or
principal place (e.g., CA-600 ≈ Los Angeles County less Glendale/Pasadena/Long
Beach; WA-500 = King County; NY-600 = New York City). Multi-county CoCs
(e.g., CO-503 Metro Denver, TX-700 Houston) were **excluded** from the model
panel to avoid denominator error in the per-capita rate. This is the same class
of caveat already noted in the implementation plan re: ACS↔CoC geography.

## Structural outlier (disclosed, retained)
NY-600 (New York City) operates under a legal right-to-shelter, so its
homelessness is shelter-policy-driven (97% sheltered) rather than primarily
economically-driven. It is retained in the panel; the model under-predicts NYC,
which is surfaced as a residual/scope insight rather than hidden.

## Flow rates: HUD System Performance Measures (SPM), CA-600
- **Source:** HUD CoC Performance Profile, CA-600 Los Angeles City & County CoC.
- **URL:** https://files.hudexchange.info/reports/published/CoC_Perf_CoC_CA-600-2023_CA_2023.pdf
- **Vintage:** FY2023 (HMIS-reported System Performance Measures).
- **Values used to calibrate transition rates + inflow in config/params.yaml:**
  - **M5 — People homeless for the first time:** 29,818 / yr → **2,485 / month** external
    inflow into the system. (Independently corroborates the ACS→PIT ML model's ~2,817/mo
    prediction within ~13%.)
  - **M7 — Exit rate ES/SH/TH/RRH → permanent housing:** 32.8% / yr → monthly hazard
    1−(1−0.328)^(1/12) ≈ **0.033 / mo** (sets sheltered→exited_positive).
  - **M1 — Avg length of time homeless:** 311 days ≈ 10.2 months → total sheltered exit
    hazard ≈ 0.098/mo; net of the 0.033 exit-to-PH, the model-consistent
    sheltered→unsheltered hazard ≈ **0.065 / mo**.
  - **M2 — Returns to homelessness within 6 months:** 7.5% → monthly return hazard
    1−(1−0.075)^(1/6) ≈ **0.013 / mo** (sets a new exited_positive→at_risk return edge).
- **PIT time series (for the backtest / face validity):** 2023 total 71,320 → 2024 total
  71,201 (HUD PopSub). The backtest seeds 2023 compartments and checks the 12-month
  forward run brackets the observed 2024 total.

## Per-person cost anchors (for config/params.yaml costs, CA-600)
Sourced separately at calibration time from published Los Angeles cost studies
(see inline `source:`/`confidence:` tags in `config/params.yaml`).
