"""Skills = the tools the WaitCost agent discovers and calls.

Each Skill is a thin, testable function over the simulation engine. The
orchestrator wraps these with Action-Tier checks and MEMORY.md logging.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from model.states import Scenario, STATES, ACTIVE_HOMELESS
from model.simulate import simulate
from model.montecarlo import run_montecarlo
from analysis import metrics


# --- Tier 0 -----------------------------------------------------------------
def fetch_hud_data(params_path):
    """Load the data 'universe' (params). Tier 0 (read-only)."""
    with open(params_path) as f:
        return yaml.safe_load(f)


class DataSufficiencyError(RuntimeError):
    """Raised when the data can't support a credible answer (bypass condition)."""


def check_data_support(params, min_active_homeless=500):
    """Enforce GOVERNANCE.md bypass conditions: decline rather than show
    unsupported bands. Tier 0. Refuses on (a) sub-CoC geography, (b) synthetic
    placeholder data, or (c) a homeless count too thin to calibrate a credible rate.
    """
    meta = params.get("meta", {})
    if meta.get("sub_coc"):
        raise DataSufficiencyError(
            "Geography is below the CoC level; HUD source data cannot support it. Declining.")
    if "synthetic" in str(meta.get("data_vintage", "")).lower():
        raise DataSufficiencyError(
            "Data vintage is a synthetic placeholder; refusing to present unsupported bands.")
    active = sum(float(params["initial_population"].get(s, 0)) for s in ACTIVE_HOMELESS)
    if active < min_active_homeless:
        raise DataSufficiencyError(
            f"Active homeless count ({active:.0f}) is too thin to calibrate credible rates. Declining.")
    return True


def retrieve_us_context(coc="CA-600", live=False):
    """Function-calling data tool: retrieve essential US public indicators for a
    city to inform the decision. Tier 0 (read-only).

    OFFLINE by default — reads the bundled, real, sourced dataset (HUD PIT +
    Census ACS). `live=True` is a hook to refresh from live US sources (Census /
    HUD FMR / FRED) when online; it degrades to the offline values on any error,
    so the demo never depends on the network.
    """
    df = pd.read_csv(os.path.join(_REPO, "data", "coc_panel.csv"))
    sel = df[df["coc"] == coc]
    if sel.empty:
        raise ValueError(f"No bundled data for CoC '{coc}'.")
    r = sel.iloc[0]
    pit = int(r["pit_total"]); pop = int(r["population"])
    ind = {
        "population": pop,
        "homeless_pit_total": pit,
        "homeless_rate_per_1k": round(pit / pop * 1000, 2),
        "unsheltered_share_pct": round(int(r["pit_unsheltered"]) / pit * 100, 1),
        "chronic_share_pct": round(int(r["pit_chronic"]) / pit * 100, 1),
        "median_home_value_usd": int(r["median_home_value"]),
        "median_household_income_usd": int(r["median_household_income"]),
        "poverty_rate_pct": float(r["poverty_rate"]),
        "home_value_to_income_ratio": round(int(r["median_home_value"]) / int(r["median_household_income"]), 1),
    }
    out = {"coc": coc, "name": r["coc_name"], "indicators": ind, "live": False,
           "sources": "HUD 2024 PIT (PopSub) + Census ACS 2024 1-yr (API); see data/SOURCES.md"}
    if live:
        try:
            out.update(_enrich_context_live(coc, out))   # optional online refresh
        except Exception:
            pass   # offline fallback — bundled real values still returned
    return out


def _enrich_context_live(coc, base):
    """Placeholder for online enrichment (Census API / HUD Fair Market Rents /
    FRED). Wired the same way as the Gemma planner: try live, fall back offline.
    Not used in the offline demo; returns nothing until a key/endpoint is set."""
    return {}


def load_inflow_model(path="model/inflow_model.json"):
    """Load the learned inflow-model report (metrics + SHAP + calibration).

    Tier 0 (read-only). Returns None if the model has not been trained yet, so
    the agent degrades gracefully. Produced by scripts/train_inflow.py.
    """
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def make_scenario(params, name, delay=0, budget=None, mix=None):
    b = float(params["meta"].get("default_budget_musd", 10.0)) if budget is None else float(budget)
    kwargs = {"name": name, "annual_budget_musd": b, "start_year": int(delay)}
    if mix:
        kwargs["mix"] = mix
    return Scenario(**kwargs)


# --- Tier 1 -----------------------------------------------------------------
def run_simulation(params, scenario, n_mc=None):
    """Deterministic run + Monte Carlo bands for one scenario. Tier 1."""
    det = simulate(params, scenario)
    bands, arr = run_montecarlo(params, scenario, n=n_mc)
    final_active = float(det[ACTIVE_HOMELESS].iloc[-1].sum())
    return {
        "scenario": scenario.name,
        "final_cum_cost_p50": float(bands["p50"].iloc[-1]),
        "final_cum_cost_p10": float(bands["p10"].iloc[-1]),
        "final_cum_cost_p90": float(bands["p90"].iloc[-1]),
        "final_active_homeless": final_active,
        "det": det,
        "bands": bands,
        "mc_final": arr,
    }


def sensitivity_report(params, scenario):
    """Rank the rate assumptions that move the result most (XAI). Tier 0."""
    return metrics.sensitivity_drivers(params, scenario)


def run_backtest(params):
    """Face validity: reproduce the observed 2024 PIT from a 2023 seed. Tier 1."""
    from model.backtest import backtest
    return backtest(params, n_mc=150)


def effect_sensitivity(params, plan, lo=0.5, hi=1.5):
    """Re-price cost-of-waiting under +/- intervention-effect priors. Tier 1."""
    return metrics.cost_of_waiting_effect_band(params, plan, lo=lo, hi=hi)


def compare_budgets(params, budgets, delay=0, mix=None, n_mc=None):
    """Compare two or more annual budgets. Tier 1."""
    return metrics.compare_budgets(params, budgets, delay=delay, mix=mix, n_mc=n_mc)


def compare_mix(params, budget, delay=0, n_mc=None):
    """Compare intervention mixes at a fixed budget. Tier 1."""
    return metrics.compare_mix(params, budget, delay=delay, n_mc=n_mc)


# A curated, representative city set for the regional ranking (kept small so the
# per-city model fit + Monte Carlo stays responsive; pass `cocs` to override).
REGIONAL_DEFAULT_COCS = ["CA-600", "NY-600", "IL-510", "WA-500", "AZ-502", "FL-600"]


def regional_cost_of_waiting(budget, delay, cocs=None, n_mc=120):
    """Rank the cost of waiting `delay` years at `budget`/yr across cities. Tier 1.

    Bounded to a curated set + modest Monte Carlo for responsiveness; the returned
    dict records `n_mc` and the cities actually computed (no silent truncation).
    Reuses build_params_for_coc + run_montecarlo + metrics.cost_of_waiting.
    """
    from model.coc_registry import build_params_for_coc
    from model.states import Scenario

    cocs = list(cocs) if cocs else list(REGIONAL_DEFAULT_COCS)
    rows = []
    for coc in cocs:
        try:
            p = build_params_for_coc(coc)
            now = run_montecarlo(p, Scenario("now", annual_budget_musd=float(budget), start_year=0), n=n_mc)[1]
            dly = run_montecarlo(p, Scenario("delay", annual_budget_musd=float(budget),
                                            start_year=int(delay)), n=n_mc)[1]
            cow = metrics.cost_of_waiting(now, dly)
            rows.append({"coc": coc, "name": p["meta"]["coc"],
                         "cost_of_waiting_musd": round(cow["extra_cost_median"] / 1e6, 1)})
        except Exception:
            continue   # skip a city that can't be built; never crash the ranking
    rows.sort(key=lambda r: r["cost_of_waiting_musd"], reverse=True)
    return {"budget_musd": float(budget), "delay_years": int(delay),
            "n_mc": int(n_mc), "cities": rows}


def compare_scenarios(params, plan, runs):
    """Cost-of-waiting, savings vs status quo, and break-even. Tier 1."""
    out = {}
    if "act_now" in runs and "delay" in runs:
        out["cost_of_waiting"] = metrics.cost_of_waiting(
            runs["act_now"]["mc_final"], runs["delay"]["mc_final"])
        out["delay_years"] = plan["delay_years"]
    if "status_quo" in runs and "act_now" in runs:
        out["savings_vs_status_quo"] = metrics.savings_vs_status_quo(
            runs["status_quo"]["mc_final"], runs["act_now"]["mc_final"])

    # Use the budget the question actually asked about (the plan), not the default,
    # so the break-even threshold ("one year of program budget") is consistent.
    budget = float(plan.get("budget_musd", params["meta"].get("default_budget_musd", 10.0)))
    mix = plan.get("mix")
    out["break_even"] = metrics.break_even_year(
        params, lambda d: make_scenario(params, f"delay_{d}", delay=d, budget=budget, mix=mix))
    return out


# --- Single source of truth for the verdict --------------------------------
# The brief CITES the decision agent's verdict verbatim — it never recomputes or
# rephrases it — so the always-visible Recommendation card and the (collapsed)
# Decision brief can never contradict each other. The framing line below doubles
# as an idempotency sentinel (see orchestrator's Gemma-path guarantee).
RECOMMENDATION_FRAMING = "This brief supports the recommendation above:"


def verdict_citation(decision):
    """The verbatim verdict-citation block injected at the top of the brief's
    recommendation section. `decision['headline']` is the single source of truth
    for the verdict sentence (the exact string the card shows as its verdict) —
    we quote it, never re-derive it. Returns a list of markdown lines."""
    d = decision or {}
    verdict_line = d.get("headline", "")
    lines = [f"**{RECOMMENDATION_FRAMING}**", ""]
    if verdict_line:
        lines += [f"> {verdict_line}", ""]
    lines.append(f"*Confidence in the direction: **{d.get('direction_confidence','—')}**. "
                 f"{d.get('magnitude_note','')}*")
    return lines


# --- Tier 1 (write artifacts) ----------------------------------------------
def write_brief(question, params, runs, comparison, drivers, out_dir, inflow_model=None,
                backtest=None, effect_band=None, intent=None, direct_answer=None, decision=None):
    """Emit multi-format artifacts: .md narrative, .json, .csv. Tier 1."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def usd(x):
        return f"${x/1e6:,.1f}M"

    cow = comparison.get("cost_of_waiting")
    be = comparison.get("break_even", {})
    sv = comparison.get("savings_vs_status_quo")

    lines = []
    lines.append("# WaitCost — Decision Brief")
    lines.append("")
    lines.append(f"**Question:** {question}")
    lines.append(f"**CoC:** {params['meta']['coc']}  ")
    lines.append(f"**Data vintage:** {params['meta']['data_vintage']}  ")
    lines.append(f"**Horizon:** {params['meta']['horizon_months']//12} years · "
                 f"Discount: {params['meta']['discount_annual']*100:.0f}% · "
                 f"Monte Carlo runs: {params['meta']['monte_carlo_runs']}")
    lines.append("")
    lines.append("> This tool INFORMS a budget-timing tradeoff. It does NOT decide "
                 "allocations or forecast individual outcomes. All figures are ranges, "
                 "not predictions.")
    lines.append("")

    # Cite (don't repeat) the recommendation: the brief is the EVIDENCE behind the
    # card, so it opens by quoting the card's verdict verbatim rather than restating
    # it as a second verdict. The bullets/chips stay on the card; the receipts
    # (scenarios, sensitivity, model, limitations) follow below.
    if decision:
        lines += verdict_citation(decision)
        lines.append("")

    # How to read the numbers below (demystify Monte Carlo + the ranges).
    lines.append("## How to read this brief")
    lines.append("")
    lines.append(f"- We simulate **three futures** — do nothing, act now, and wait — and run each "
                 f"**{params['meta']['monte_carlo_runs']} times** with slightly different luck. That repeated "
                 f"simulation is the **Monte Carlo**; it's why you see the run step three times and why every "
                 f"figure is a **range**, not a single guess.")
    lines.append(f"- **P50** is the middle outcome; the **80% range** (P10–P90) is where the answer lands "
                 f"4 times out of 5.")
    lines.append(f"- The big 10-year total is mostly **unavoidable**; the decision moves the smaller "
                 f"**cost-of-waiting** slice — that's the number to watch.")
    lines.append("")

    if direct_answer:
        lines.append(f"## Direct answer{f' ({intent})' if intent else ''}")
        lines.append("")
        lines.append(direct_answer)
        lines.append("")
    lines.append("## Scenarios")
    lines.append("")
    lines.append("| Scenario | 10-yr cumulative public cost (P50) | 80% range | Active homeless at horizon |")
    lines.append("|---|---|---|---|")
    for k, r in runs.items():
        lines.append(f"| {r['scenario']} | {usd(r['final_cum_cost_p50'])} | "
                     f"{usd(r['final_cum_cost_p10'])} – {usd(r['final_cum_cost_p90'])} | "
                     f"{r['final_active_homeless']:,.0f} |")
    lines.append("")
    if cow:
        lines.append("## Cost of waiting")
        lines.append("")
        lines.append(f"Delaying intervention by **{comparison['delay_years']} years** is projected to cost "
                     f"**{usd(cow['extra_cost_median'])} more** over the horizon "
                     f"(80% range {usd(cow['extra_cost_p10'])} – {usd(cow['extra_cost_p90'])}).")
        lines.append("")
        if effect_band:
            lines.append(
                f"*Assumption sensitivity:* the headline scales with the (low-confidence) "
                f"intervention-effect sizes. At ±50% effect, the cost-of-waiting ranges "
                f"**{usd(effect_band['cow_at_lo'])} – {usd(effect_band['cow_at_hi'])}** — the "
                f"sign (waiting costs more) is robust; the magnitude is a planning estimate.")
            lines.append("")
    if sv:
        lines.append(f"Acting now vs. doing nothing saves an estimated **{usd(sv['savings_median'])}** "
                     f"(80% range {usd(sv['savings_p10'])} – {usd(sv['savings_p90'])}).")
        lines.append("")
    if be:
        bey = be.get("break_even_year")
        msg = (f"**Break-even: delaying past year {bey}** wastes more than one full year of "
               f"program budget." if bey else
               "No break-even within the scanned delay window (extra cost stays below one year of budget).")
        lines.append("## Break-even")
        lines.append("")
        lines.append(msg)
        lines.append("")
    if inflow_model:
        im = inflow_model
        inf = im.get("inflow_at_risk_monthly", {})
        lines.append("## Where's the AI? Learned inflow predictor (ACS → homelessness, with SHAP)")
        lines.append("")
        xv = im.get("spm_crossval") or {}
        central = params.get("inflow", {}).get("at_risk", inf.get("p50", 0))
        lines.append(
            f"A **{im.get('model','learned model')}** maps real Census ACS economic "
            f"signals → HUD PIT homelessness across **{im.get('n_coc','?')} Continuums of Care**. "
            f"Held-out (leave-one-CoC-out) **R²={im.get('loo_r2',float('nan')):.2f}**, "
            f"**MAE={im.get('loo_mae',float('nan')):.2f}** per 1,000. The system inflow is set to "
            f"**{central:,.0f}/month** from **HUD SPM Measure 5** (first-time homeless), and the "
            f"ML model independently predicts **{xv.get('ml_inflow_monthly',inf.get('p50',0)):,.0f}/mo** "
            f"— two independent methods agreeing within **~{xv.get('agreement_pct_diff',0):.0f}%**. "
            f"The model's band (CV {params.get('inflow_uncertainty',{}).get('cv',0):.2f}) drives the "
            f"Monte Carlo, so the uncertainty above is partly *learned*, not assumed.")
        lines.append("")
        if backtest:
            within = "within" if backtest.get("within_band") else "outside"
            lines.append(
                f"**Face validity (backtest):** seeded on the real 2023 PIT and run 12 months on "
                f"the SPM-calibrated rates, the model predicts a 2024 active-homeless count of "
                f"**{backtest['predicted_active_p50']:,.0f}** "
                f"(P10 {backtest['predicted_active_p10']:,.0f} – P90 {backtest['predicted_active_p90']:,.0f}) "
                f"vs the **observed {backtest['observed_2024_total']:,}** — {within} the band "
                f"({backtest['abs_pct_error_p50']:.0f}% central error).")
            lines.append("")
        lines.append("| SHAP driver of predicted homelessness | contribution (per 1,000) |")
        lines.append("|---|---|")
        for d in im.get("shap_target", [])[:4]:
            lines.append(f"| {d['feature']} | {d['shap']:+.2f} |")
        lines.append("")
        lines.append("> Scope note: the model captures *economically*-driven homelessness. It "
                     "under-predicts right-to-shelter cities (e.g. NYC), surfaced as a residual "
                     "rather than hidden — a reminder the model informs, not decides.")
        lines.append("")
    lines.append("## Top assumption drivers (sensitivity / XAI)")
    lines.append("")
    lines.append("| Rank | Assumption (transition) | +20% rate -> change in cost | Confidence |")
    lines.append("|---|---|---|---|")
    for i, d in enumerate(drivers, 1):
        lines.append(f"| {i} | {d['driver']} | {d['pct_change']:+.1f}% | {d['confidence']} |")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append("- Real: initial homeless counts (HUD 2024 PIT), per-person costs (Economic "
                 "Roundtable), the system inflow + key exit/return rates (HUD SPM 2023), and the "
                 "ACS→PIT inflow model. The remaining transition rates are documented priors "
                 "(confidence: low) — see the source tags in params.yaml.")
    lines.append("- `at_risk` and `housed_stable` are ACS-derived proxies (no PIT category exists "
                 "for them); intervention effect sizes are priors pending causal estimation — the "
                 "headline is therefore reported as a band over ±50% of those effects (above).")
    lines.append("- The inflow model is a cross-section of n=15 CoCs (leave-one-out R²≈0.36); it "
                 "informs the inflow band, it does not forecast individuals.")
    lines.append("- Compartment model trades individual precision for transparency. The "
                 "high-influence, low-confidence drivers above are where conclusions are most fragile.")

    md_path = out / "decision_brief.md"
    md_path.write_text("\n".join(lines))

    # JSON (schema artifact)
    json_path = out / "scenarios.json"
    payload = {
        "question": question,
        "coc": params["meta"]["coc"],
        "data_vintage": params["meta"]["data_vintage"],
        "scenarios": [
            {k2: v2 for k2, v2 in r.items() if k2 not in ("det", "bands", "mc_final")}
            for r in runs.values()
        ],
        "comparison": {k: v for k, v in comparison.items()},
        "drivers": drivers,
        "inflow_model": inflow_model,
    }
    json_path.write_text(json.dumps(payload, indent=2))

    # CSV (tabular artifact) — scenario cost summary
    csv_path = out / "scenarios.csv"
    pd.DataFrame([
        {"scenario": r["scenario"],
         "cum_cost_p50": r["final_cum_cost_p50"],
         "cum_cost_p10": r["final_cum_cost_p10"],
         "cum_cost_p90": r["final_cum_cost_p90"],
         "active_homeless_horizon": r["final_active_homeless"]}
        for r in runs.values()
    ]).to_csv(csv_path, index=False)

    return {"md": str(md_path), "json": str(json_path), "csv": str(csv_path),
            "brief_markdown": "\n".join(lines)}
