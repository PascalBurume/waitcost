# Governance & Action Tiers (skill reference)

This is the governance contract the WaitCost skill operates under. It mirrors the
repo's top-level `GOVERNANCE.md`; the enforcement lives in Python, not in prose.

## Action Tiers (autonomy bounds)
- **Tier 0** — read data, sensitivity/uncertainty analysis — automatic.
- **Tier 1** — run simulations, compare budgets/mixes, write briefs — automatic.
- **Tier 2+** — recommend or finalize a specific binding allocation — **human
  approval required**. The CLI runs at `max_auto_tier=1`; a Tier-2 step raises
  unless `--approve-allocation` is passed, which you must only do after the user
  explicitly confirms they want a binding recommendation.

## Bypass conditions (when the engine declines) — ENFORCED IN CODE
The engine warns and declines rather than show unsupported bands when:
- input data for a population is too thin to calibrate a credible transition rate;
- geography is below the level the source data supports (sub-CoC);
- the data vintage is a synthetic placeholder.

Enforced by `skills.check_data_support()` in Stage 1 of every answer (raises
`DataSufficiencyError`; the orchestrator returns `{"declined": true, ...}`). If
the CLI returns a declined result, relay its `reason` — do not work around it.

## Number-guard
Every figure is the engine's. The skill must not introduce, round, or recompute a
dollar figure. The `guard` subcommand reuses `planner.numbers_are_grounded` so a
drafted memo can be checked for invented numbers.

## Responsible-AI notes (F-taxonomy)
- F3 Privacy: aggregate CoC data only; never individual-level records.
- F4 Robustness: a crafted prompt cannot override the Tier-2 approval gate (it is
  a Python guard, not an instruction).
- F6 Transparency: every figure ships with assumptions + uncertainty.
- F8 Over-caution: do not refuse legitimate population-level scenarios.
