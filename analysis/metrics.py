"""Decision-relevant metrics: cost of waiting, break-even, sensitivity drivers."""
import numpy as np

from model.simulate import simulate, build_base_rates


def cost_of_waiting(arr_now, arr_delay):
    """Compare final cumulative cost of acting now vs delaying (Monte Carlo arrays)."""
    final_now = arr_now[:, -1]
    final_delay = arr_delay[:, -1]
    diff = final_delay - final_now
    return {
        "now_median": float(np.median(final_now)),
        "delay_median": float(np.median(final_delay)),
        "extra_cost_median": float(np.median(diff)),
        "extra_cost_p10": float(np.percentile(diff, 10)),
        "extra_cost_p90": float(np.percentile(diff, 90)),
    }


def cost_composition(params, scenario):
    """Split a scenario's 10-year cumulative discounted public cost by state, so a
    chart can show WHERE the money goes (chronic / unsheltered / sheltered / ...).
    Reuses simulate's per-state cost columns — the parts sum to the same total."""
    from model.states import STATES
    df = simulate(params, scenario, with_composition=True)
    by_state = {s: float(df[f"cost__{s}"].sum()) for s in STATES}
    return {"by_state": by_state, "total": float(sum(by_state.values()))}


def cost_of_waiting_sweep(params, budgets, delay, n_mc=None):
    """Cost of waiting `delay` years for EACH budget. Reuses cost_of_waiting (the
    same primitive the single-budget path uses) per budget, so each row equals a
    single-budget run. Used by the multi-budget answer and its chart."""
    from model.states import Scenario
    from model.montecarlo import run_montecarlo
    rows = []
    for b in budgets:
        now = run_montecarlo(params, Scenario(f"now_{b}", annual_budget_musd=float(b), start_year=0), n=n_mc)[1]
        dly = run_montecarlo(params, Scenario(f"delay_{b}", annual_budget_musd=float(b),
                                              start_year=int(delay)), n=n_mc)[1]
        rows.append({"budget_musd": float(b), **cost_of_waiting(now, dly)})
    return {"delay_years": int(delay), "rows": rows}


def savings_vs_status_quo(arr_status_quo, arr_now):
    """Median savings (and band) from acting now vs doing nothing."""
    diff = arr_status_quo[:, -1] - arr_now[:, -1]
    return {
        "savings_median": float(np.median(diff)),
        "savings_p10": float(np.percentile(diff, 10)),
        "savings_p90": float(np.percentile(diff, 90)),
    }


def break_even_year(params, make_scenario, max_delay=10):
    """Smallest delay (years) whose extra cost exceeds one year of program budget."""
    base = float(simulate(params, make_scenario(0))["cum_cost"].iloc[-1])
    annual_budget = make_scenario(0).annual_budget_musd * 1e6
    table, be = [], None
    for d in range(0, max_delay + 1):
        c = float(simulate(params, make_scenario(d))["cum_cost"].iloc[-1])
        extra = c - base
        table.append({"delay_years": d, "extra_cost_vs_now": extra})
        if be is None and d > 0 and annual_budget > 0 and extra > annual_budget:
            be = d
    return {"break_even_year": be, "annual_budget_usd": annual_budget, "table": table}


_MIXES = {
    "prevention-heavy": {"prevention": 0.60, "rapid_rehousing": 0.20, "permanent_supportive_housing": 0.20},
    "rapid-rehousing-heavy": {"prevention": 0.20, "rapid_rehousing": 0.60, "permanent_supportive_housing": 0.20},
    "supportive-housing-heavy": {"prevention": 0.20, "rapid_rehousing": 0.20, "permanent_supportive_housing": 0.60},
    "balanced": {"prevention": 0.34, "rapid_rehousing": 0.33, "permanent_supportive_housing": 0.33},
}


def compare_budgets(params, budgets, delay=0, mix=None, n_mc=None):
    """Compare annual budgets: 10-yr cost + savings vs doing nothing for each."""
    from model.states import Scenario
    from model.montecarlo import run_montecarlo

    sq = run_montecarlo(params, Scenario("sq", annual_budget_musd=0.0), n=n_mc)[1][:, -1]
    rows = []
    for b in budgets:
        kw = {"annual_budget_musd": float(b), "start_year": int(delay)}
        if mix:
            kw["mix"] = mix
        now = run_montecarlo(params, Scenario(f"now_{b}", **kw), n=n_mc)[1][:, -1]
        rows.append({"budget_musd": float(b),
                     "cum_cost_p50": float(np.median(now)),
                     "savings_vs_nothing_p50": float(np.median(sq - now))})
    best = min(rows, key=lambda r: r["cum_cost_p50"])
    return {"budgets": rows, "best_budget_musd": best["budget_musd"], "delay_years": int(delay)}


def compare_mix(params, budget, delay=0, n_mc=None):
    """Compare intervention mixes at a fixed budget: which yields lowest 10-yr cost."""
    from model.states import Scenario
    from model.montecarlo import run_montecarlo

    rows = []
    for name, m in _MIXES.items():
        now = run_montecarlo(params, Scenario(f"mix_{name}", annual_budget_musd=float(budget),
                                              start_year=int(delay), mix=m), n=n_mc)[1][:, -1]
        rows.append({"mix": name, "cum_cost_p50": float(np.median(now))})
    best = min(rows, key=lambda r: r["cum_cost_p50"])
    return {"mixes": rows, "best_mix": best["mix"], "budget_musd": float(budget)}


def cost_of_waiting_effect_band(params, plan, lo=0.5, hi=1.5):
    """Re-price the cost-of-waiting under scaled intervention-effect priors.

    The effect sizes are the model's weakest (low-confidence) inputs, and the
    headline scales with them. We therefore report the cost-of-waiting as a band
    over +/- a multiple of the effect sizes, so the number is presented as a
    range driven by the known-weak assumption, not a false-precision point.
    """
    import copy
    from model.states import Scenario
    from model.montecarlo import run_montecarlo

    budget = float(plan.get("budget_musd", params["meta"].get("default_budget_musd", 10.0)))
    delay = int(plan["delay_years"])

    def cow_for_scale(scale):
        p = copy.deepcopy(params)
        for cfg in p["interventions"].values():
            cfg["effect_per_million_per_month"] *= scale
        now = run_montecarlo(p, Scenario("now", annual_budget_musd=budget, start_year=0))[1][:, -1]
        dly = run_montecarlo(p, Scenario("delay", annual_budget_musd=budget, start_year=delay))[1][:, -1]
        return float(np.median(dly - now))

    return {"effect_lo": lo, "effect_hi": hi, "delay_years": delay,
            "cow_base": cow_for_scale(1.0),
            "cow_at_lo": cow_for_scale(lo),
            "cow_at_hi": cow_for_scale(hi)}


def benefit_cost_ratio(savings, spend):
    """Benefit-cost ratio = avoided public cost / total program spend (both $).

    > 1 means acting now pays back; <= 0 spend or negative savings returns None
    (the caller explains 'doesn't pay back at this scale')."""
    if spend <= 0 or savings is None:
        return None
    return savings / spend


def sensitivity_drivers(params, scenario, bump=0.20, top=5):
    """One-at-a-time: bump each rate +bump, rank by change in final cumulative cost (XAI)."""
    baseline = float(simulate(params, scenario)["cum_cost"].iloc[-1])
    drivers = []
    for t in params["transitions"]:
        key = (t["from"], t["to"])
        ov = {key: 1.0 + bump}
        bumped = float(simulate(params, scenario, rate_overrides=ov)["cum_cost"].iloc[-1])
        drivers.append({
            "driver": f"{t['from']} -> {t['to']}",
            "pct_change": (bumped - baseline) / baseline * 100 if baseline else 0.0,
            "confidence": t.get("confidence", "low"),
        })
    drivers.sort(key=lambda d: abs(d["pct_change"]), reverse=True)
    return drivers[:top]
