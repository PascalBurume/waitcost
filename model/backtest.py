"""Backtest / face validity for CA-600.

Seed the model with the REAL 2023 HUD PIT compartments, run 12 months forward on
the calibrated parameters (no new intervention), and check the predicted active
homeless count brackets the REAL observed 2024 PIT total. This is the historical
face-validity check the implementation plan called for.

Data (HUD PopSub CA-600):
  2023 PIT: sheltered 19,013; unsheltered (non-chronic) 25,292; chronic-unsheltered
            27,015  -> total 71,320.
  2024 PIT: total 71,201  (the target the 12-month run must bracket).
"""
import copy

import numpy as np

from model.states import Scenario, ACTIVE_HOMELESS
from model.simulate import simulate
from model.montecarlo import sample_rate_overrides, sample_inflow_scale

# Real 2023 seed (homeless compartments from HUD PopSub; at_risk/housed proxies
# carried from params, slow-moving structural pools).
CA600_2023_SEED = {
    "housed_stable": 1204170,
    "at_risk": 96334,
    "sheltered": 19013,
    "unsheltered": 25292,
    "chronic_unsheltered": 27015,
    "exited_positive": 0,
}
OBSERVED_2024_TOTAL = 71201


def backtest(params, seed_pop=None, horizon_months=12, n_mc=200):
    seed_pop = dict(seed_pop or CA600_2023_SEED)
    p = copy.deepcopy(params)
    p["meta"] = dict(p["meta"])
    p["meta"]["horizon_months"] = int(horizon_months)
    p["initial_population"] = seed_pop
    sc = Scenario(name="backtest", annual_budget_musd=0.0)   # status quo

    det = simulate(p, sc)
    pred_det = float(det[ACTIVE_HOMELESS].iloc[-1].sum())

    rng = np.random.default_rng(int(p["meta"]["seed"]))
    finals = []
    for _ in range(int(n_mc)):
        ov = sample_rate_overrides(p, rng)
        isc = sample_inflow_scale(p, rng)
        d = simulate(p, sc, rate_overrides=ov, inflow_scale=isc)
        finals.append(float(d[ACTIVE_HOMELESS].iloc[-1].sum()))
    finals = np.array(finals)
    p10, p50, p90 = (float(np.percentile(finals, q)) for q in (10, 50, 90))
    obs = OBSERVED_2024_TOTAL
    return {
        "seed_total": sum(seed_pop[s] for s in ACTIVE_HOMELESS),
        "predicted_active_det": pred_det,
        "predicted_active_p10": p10,
        "predicted_active_p50": p50,
        "predicted_active_p90": p90,
        "observed_2024_total": obs,
        "abs_pct_error_p50": abs(p50 - obs) / obs * 100.0,
        "within_band": bool(p10 <= obs <= p90),
    }
