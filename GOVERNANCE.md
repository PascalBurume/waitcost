# Governance & Lifecycle

Designed for what happens *after* the demo — the grad-level differentiator.

## Ownership
- A named model owner approves any change to `config/params.yaml`.
- All parameter changes go through review (PR + at least one approval) and are
  recorded in `MEMORY.md` and version control.

## Recalibration cadence
- Re-fit transition rates when each annual HUD PIT/SPM release lands.
- `params.yaml` carries a `data_vintage`; every brief records the vintage used, so
  results are reproducible and traceable.

## Drift detection
- Each cycle, log predicted vs. realized stock changes.
- Alert when divergence exceeds a set threshold — a signal that assumptions have
  gone stale and the model needs recalibration before further use.

## Action Tiers (autonomy bounds)
- Tier 0: read data, sensitivity analysis — automatic.
- Tier 1: run simulations, write briefs — automatic.
- Tier 2+: recommend or finalize an allocation — **human approval required**.

## Bypass conditions (when NOT to use) — ENFORCED IN CODE
- Input data for a population is too thin to calibrate a credible transition rate.
- Geography is below the level the source data supports (sub-CoC).
- Data vintage is a synthetic placeholder.
- In these cases the agent **warns and declines** rather than showing unsupported bands.
- Enforcement: `skills.check_data_support()` runs in Stage 1 of every answer and raises
  `DataSufficiencyError`; the orchestrator returns a `declined` result. Covered by tests
  (`test_bypass_declines_thin_data`, `test_bypass_declines_sub_coc`,
  `test_agent_declines_gracefully_on_thin_data`).

## Validation (face validity)
- Backtest: seed real 2023 PIT, run 12 months on the SPM-calibrated rates, confirm the
  predicted 2024 active-homeless count brackets the observed 2024 PIT (`model/backtest.py`,
  `scripts/backtest.py`, `test_backtest_brackets_observed_2024`). Re-run each PIT release.

## Responsible-AI risk register (F-taxonomy)
- F3 Privacy: aggregate CoC data only; no individual-level records.
- F4 Robustness: a crafted prompt cannot override model limits or the approval gate.
- F6 Transparency: every figure ships with assumptions + uncertainty.
- F8 Over-caution: do not refuse legitimate scenarios (over-refusal is also a failure).
