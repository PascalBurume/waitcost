"""Monte Carlo wrapper: sample uncertain rates -> cumulative-cost bands."""
import numpy as np
import pandas as pd

from model.simulate import simulate

# How wide we sample each rate, by its confidence tag.
CONF_SIGMA = {"low": 0.30, "med": 0.15, "high": 0.05}


def sample_rate_overrides(params, rng):
    """Lognormal multiplier per transition (median ~1), width set by confidence."""
    ov = {}
    for t in params["transitions"]:
        sigma = CONF_SIGMA.get(t.get("confidence", "low"), 0.30)
        ov[(t["from"], t["to"])] = float(rng.lognormal(mean=-0.5 * sigma ** 2, sigma=sigma))
    return ov


def sample_inflow_scale(params, rng):
    """Lognormal multiplier (median ~1) on the at-risk inflow.

    Width comes from the LEARNED inflow model's prediction interval
    (params['inflow_uncertainty']['cv']), so the resulting cost bands are partly
    model-derived rather than hand-set. Absent that key, returns 1.0 (no-op).
    """
    cv = float(params.get("inflow_uncertainty", {}).get("cv", 0.0))
    if cv <= 0.0:
        return 1.0
    return float(rng.lognormal(mean=-0.5 * cv ** 2, sigma=cv))


def run_montecarlo(params, scenario, n=None, seed=None):
    """Return (bands_df, final_cum_array). bands_df has p10/p50/p90 cumulative cost."""
    n = int(params["meta"]["monte_carlo_runs"]) if n is None else int(n)
    seed = int(params["meta"]["seed"]) if seed is None else int(seed)
    rng = np.random.default_rng(seed)

    trajectories = []
    for _ in range(n):
        ov = sample_rate_overrides(params, rng)
        inflow_scale = sample_inflow_scale(params, rng)
        df = simulate(params, scenario, rate_overrides=ov, inflow_scale=inflow_scale)
        trajectories.append(df["cum_cost"].to_numpy())

    arr = np.vstack(trajectories)               # n x (H+1)
    bands = pd.DataFrame({
        "month": np.arange(arr.shape[1]),
        "p10": np.percentile(arr, 10, axis=0),
        "p50": np.percentile(arr, 50, axis=0),
        "p90": np.percentile(arr, 90, axis=0),
    })
    return bands, arr
