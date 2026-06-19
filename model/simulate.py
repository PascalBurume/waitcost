"""Core deterministic stock-and-flow simulation (monthly compartment model)."""
import numpy as np
import pandas as pd

from model.states import STATES
from model.interventions import intervention_bonus
from model.cost import state_cost, per_person_monthly

IDX = {s: i for i, s in enumerate(STATES)}


def build_base_rates(params, overrides=None):
    """Transition rates as {(from, to): rate}, optionally scaled by a multiplier dict."""
    overrides = overrides or {}
    rates = {}
    for t in params["transitions"]:
        key = (t["from"], t["to"])
        rates[key] = float(t["rate"]) * float(overrides.get(key, 1.0))
    return rates


def simulate(params, scenario, rate_overrides=None, inflow_scale=1.0, with_composition=False):
    """Run one deterministic trajectory. Returns a tidy monthly DataFrame.

    `inflow_scale` multiplies the external at-risk inflow; the Monte Carlo uses
    it to sample the LEARNED inflow band (default 1.0 = deterministic central).
    `with_composition=True` adds a discounted per-state cost column `cost__<state>`
    per month, so callers can split the cumulative cost by group. Off by default,
    so the Monte Carlo hot path pays nothing.
    """
    H = int(params["meta"]["horizon_months"])
    disc_m = (1.0 + float(params["meta"]["discount_annual"])) ** (1 / 12) - 1.0
    dmult = float(params["costs"]["duration_multiplier_per_year"])
    base_cost = np.array([params["costs"]["base_monthly"][s] for s in STATES], float)

    stocks = np.array([params["initial_population"][s] for s in STATES], float)
    tenure = np.zeros(len(STATES))                       # mean years-in-state
    base_rates = build_base_rates(params, rate_overrides)
    inflow = params.get("inflow", {})
    budget_monthly = scenario.annual_budget_musd * 1e6 / 12.0

    rows = []
    cum = 0.0
    for m in range(H + 1):
        cost = state_cost(base_cost, tenure, stocks, dmult)
        spend = budget_monthly if scenario.active(m) else 0.0
        total = cost + spend
        disc = 1.0 / ((1.0 + disc_m) ** m)
        cum += total * disc

        row = {"month": m, "cost": total, "disc_cost": total * disc,
               "cum_cost": cum, "spend": spend}
        for i, s in enumerate(STATES):
            row[s] = stocks[i]
        if with_composition:
            # Discounted public cost attributed to each state this month (same
            # per-person × stocks × duration the total uses — it sums to `cost`).
            pp = per_person_monthly(base_cost, tenure, dmult)
            for i, s in enumerate(STATES):
                row[f"cost__{s}"] = float(pp[i] * stocks[i] * disc)
        rows.append(row)
        if m == H:
            break

        # --- advance one month ---
        rates = dict(base_rates)
        for key, b in intervention_bonus(params, scenario, m).items():
            rates[key] = rates.get(key, 0.0) + b

        delta = np.zeros(len(STATES))
        stayed = stocks.copy()
        for (frm, to), r in rates.items():
            r = max(0.0, min(r, 1.0))
            flow = stocks[IDX[frm]] * r
            delta[IDX[frm]] -= flow
            delta[IDX[to]] += flow
            stayed[IDX[frm]] -= flow
        for s, amt in inflow.items():
            delta[IDX[s]] += amt * inflow_scale

        new_stocks = np.maximum(stocks + delta, 0.0)

        # tenure: stayers age by 1/12 yr, newcomers enter at tenure 0
        new_tenure = np.zeros(len(STATES))
        for i in range(len(STATES)):
            staying = max(min(stayed[i], new_stocks[i]), 0.0)
            if new_stocks[i] > 1e-9:
                new_tenure[i] = staying * (tenure[i] + 1 / 12) / new_stocks[i]
        stocks, tenure = new_stocks, new_tenure

    return pd.DataFrame(rows)
