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

## The brain, and why no PII can leak
- The planner/narrator is **Claude Sonnet 4.6** (via the Anthropic API); a deterministic
  rule mode (`WAITCOST_PLANNER=rule`) is the air-gapped, no-network fallback and the
  guaranteed-reproducible demo.
- **No PII is even possible.** The system holds only public, aggregate HUD/Census data, and
  the safety rail forbids individual-level questions — so nothing sensitive can ever be sent
  to any API, by design rather than by promise. The engine still owns every number; the model
  only phrases and routes.

## Action Tiers (autonomy bounds)
- Tier 0: read data, sensitivity analysis, **evaluate the answer** — automatic.
- Tier 1: run simulations, write briefs — automatic.
- Tier 2+: recommend or finalize an allocation — **human approval required**.

## Answer-level checks (the Evaluator — the 5th agent) — ENFORCED IN CODE
Before any answer reaches the user, the Evaluator (`agent/evaluator.py`) checks it across six
dimensions — deterministic code for the hard guarantees, an LLM judge only for relevance:
- **Grounding** — every figure in an LLM-authored memo must trace to the engine
  (`planner.numbers_are_grounded`); else the deterministic brief is used.
- **Scope** — re-runs the safety rail; the engine must not have answered an individual/sub-CoC question.
- **Parameter fidelity** — flags any default-used / dropped value (no silent defaults; the parsed
  reading is echoed back to the user).
- **Data confidence** — labels non-calibrated cities "illustrative" and widens the read.
- **Chart–text consistency** — the headline figure must match the engine output.
- **Question-match** (LLM judge) — does the answer address the question actually asked?
On a hard failure the system **self-corrects once** (re-plan with a repair hint), then **declines**
rather than show a confident wrong answer. Confidence-gated routing **asks instead of guessing**
when the LLM and rule routers disagree at low confidence. The verdict is surfaced to the user as a
per-dimension **Response Check** panel — when the AI is unsure, the user is told *what* and *why*.
Covered by `eval/test_evaluator.py`.

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
- **F1 Accuracy / invented numbers:** the engine owns every figure; the number-guard rejects any
  number the model didn't receive (`numbers_are_grounded`), and the Evaluator re-checks grounding.
- **F3 Privacy:** aggregate CoC data only; no individual-level records — so no PII can reach the API.
  The deterministic safety rail forces `out_of_scope`, and the Evaluator re-verifies scope.
- **F4 Robustness:** a crafted prompt cannot override the safety rail (a rule veto, not the LLM) or
  the Tier-2 approval gate; the Evaluator independently re-checks both downstream of the model.
- **F6 Transparency:** every figure ships with assumptions + uncertainty, the parsed reading is
  echoed back, and the per-dimension Response Check shows what was checked and what (if anything) is off.
- **F8 Over-caution:** the Evaluator is **annotate-first** — uncertainty becomes a *warn* (answer shown
  with a caveat), and a lingering relevance doubt is downgraded to a warning, never a wrongful refusal;
  decline is reserved for true scope/data/correctness violations. Tested for over-refusal.

A fuller failure-mode register (who is harmed + the specific design choice that reduces it) is in
[EVALUATOR_AND_GUARDRAILS.md](EVALUATOR_AND_GUARDRAILS.md).
