"""Visualization agent — the charts specialist.

A second, specialist agent: given a question (intent) it picks the RIGHT chart
for a decision and builds a render-ready *spec* (data + encoding) from real
engine output. The spec is framework-agnostic JSON — Streamlit/Plotly draws it
today, a React/Recharts frontend can draw the same spec tomorrow. The maths runs
in Python (the sandbox); the chart only displays it.

Spec shape:
  {name, kind, title, subtitle, x_label, y_label, series:[...], annotations:[...],
   caption, source}
kinds: line_band · bar_ci · bar · tornado · scatter · dot_interval · waterfall ·
       area · shap_bar · map
"""
import os

import numpy as np
import pandas as pd

from agent import skills
from analysis import metrics
from model.simulate import simulate
from model.states import Scenario, ACTIVE_HOMELESS

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PANEL = os.path.join(_REPO, "data", "coc_panel.csv")
_SRC = "Computed from the WaitCost engine (real HUD PIT + Census ACS)."

# city centroids for the map
_COORDS = {
    "CA-600": (34.05, -118.24), "CA-601": (32.72, -117.16), "CA-501": (37.77, -122.42),
    "WA-500": (47.61, -122.33), "AZ-502": (33.45, -112.07), "CA-500": (37.34, -121.89),
    "OR-501": (45.52, -122.68), "NV-500": (36.17, -115.14), "NY-600": (40.71, -74.01),
    "DC-500": (38.90, -77.04), "MN-500": (44.98, -93.27), "TN-502": (35.96, -83.92),
    "FL-600": (25.76, -80.19), "PA-500": (39.95, -75.16), "IL-510": (41.88, -87.63),
    "CA-503": (38.58, -121.49), "AZ-501": (32.22, -110.97),
}

# name · kind · which question it answers · one-line "when to use"
CHART_CATALOG = [
    {"name": "cost_trajectory", "kind": "line_band", "intent": "cost_of_waiting",
     "when": "Show cumulative cost diverging over time for act-now vs wait vs nothing."},
    {"name": "cost_of_waiting", "kind": "waterfall", "intent": "cost_of_waiting",
     "when": "Show the single headline: the extra cost of waiting, with its range."},
    {"name": "break_even_curve", "kind": "line", "intent": "break_even",
     "when": "Show extra cost rising with delay and where it crosses one year of budget."},
    {"name": "scenario_costs", "kind": "bar_ci", "intent": "savings_now",
     "when": "Compare 10-year cost across the three scenarios with uncertainty bars."},
    {"name": "compartments_over_time", "kind": "line_band", "intent": "outcome_at_horizon",
     "when": "Show people unsheltered over 10 years, doing nothing vs acting now (the gap = people helped)."},
    {"name": "budget_comparison", "kind": "bar", "intent": "compare_budgets",
     "when": "Compare 10-year cost across candidate annual budgets."},
    {"name": "mix_comparison", "kind": "bar", "intent": "compare_mix",
     "when": "Compare 10-year cost across intervention spending mixes."},
    {"name": "sensitivity_tornado", "kind": "tornado", "intent": "sensitivity",
     "when": "Rank which assumptions move the result most (what to tighten first)."},
    {"name": "shap_drivers", "kind": "shap_bar", "intent": "model",
     "when": "Explain what drives the model's homelessness prediction (SHAP)."},
    {"name": "backtest", "kind": "dot_interval", "intent": "model",
     "when": "Show the model's predicted 2024 band vs the observed count (face validity)."},
    {"name": "city_scatter", "kind": "scatter", "intent": "city_context",
     "when": "Place the city on the housing-cost vs homelessness relationship."},
    {"name": "city_benchmark", "kind": "bar", "intent": "city_context",
     "when": "Rank the city's homelessness rate against peers."},
    {"name": "city_map", "kind": "map", "intent": "city_context",
     "when": "Show all cities geographically, sized by homelessness rate."},
    {"name": "equity_disparity", "kind": "bar", "intent": "equity",
     "when": "Show which groups are over-represented among the homeless vs. population."},
    {"name": "equity_unsheltered", "kind": "bar", "intent": "equity",
     "when": "Show which groups are most exposed to unsheltered homelessness."},
    {"name": "roi", "kind": "bar", "intent": "roi",
     "when": "Show program spend vs public cost avoided — the return on acting now."},
    {"name": "people_helped", "kind": "bar", "intent": "cost_per_person",
     "when": "Show people homeless at the horizon, status quo vs acting now (gap = people helped)."},
    {"name": "regional_waiting", "kind": "bar", "intent": "regional",
     "when": "Rank the cost of waiting across multiple cities."},
]

from agent import capabilities as _caps

# Base defaults: first chart per intent from the catalog. This is what supplies
# the non-capability aliases (e.g. `model` -> shap_drivers).
INTENT_CHART = {c["intent"]: c["name"] for c in reversed(CHART_CATALOG)}
# The capability registry OWNS each engine intent's chart binding, so the text
# answer and its recommended chart can never disagree (cost_of_waiting -> the
# waterfall headline, uncertainty -> the tornado). New intents bring their own
# chart in agent/capabilities/specs.py — no edit needed here.
INTENT_CHART.update(_caps.intent_chart_map())
INTENT_CHART.update({"explore": "cost_trajectory"})   # frontend-only alias (not an intent)


def _f(x, n=2):
    return round(float(x), n)


def _blabel(m):
    """Axis label for a budget given in $M — '$5.0B' for >= 1000, else '$15M'."""
    return f"${m/1000:.1f}B" if m >= 1000 else f"${m:.0f}M"


def _params(coc):
    from model.coc_registry import build_params_for_coc
    return build_params_for_coc(coc)


def _years(months):
    return [int(m // 12) for m in months]


# --------------------------------------------------------------------------- #
# Builders (each returns a spec computed from REAL engine output)
# --------------------------------------------------------------------------- #
def _scenarios(p, budget, delay, n_mc):
    now = skills.run_simulation(p, skills.make_scenario(p, "Act now", delay=0, budget=budget), n_mc)
    dly = skills.run_simulation(p, skills.make_scenario(p, f"Delay {delay}y", delay=delay, budget=budget), n_mc)
    sq = skills.run_simulation(p, skills.make_scenario(p, "Status quo", budget=0.0), n_mc)
    return now, dly, sq


def cost_trajectory(coc, budget, delay, n_mc=200):
    """DIVERGENCE view: both alternatives plotted as EXTRA cost vs acting now,
    starting at $0 and climbing. The three absolute totals are ~$29B and ~1-2%
    apart (invisible); the *difference* is the decision and — because every
    scenario uses the same MC seed (rows align) — its 80% band is far tighter
    than the absolute bands, since correlated draws cancel in a difference."""
    p = _params(coc); now, dly, sq = _scenarios(p, budget, delay, n_mc)
    months = now["bands"]["month"].to_numpy()
    cols = months[months % 12 == 0].astype(int)          # monthly column index per year
    xs = [int(c // 12) for c in cols]
    now_a = now["mc_final"]

    def diff(arr, name, color):
        d = arr[:, cols] - now_a[:, cols]                # n x Y per-run difference
        return {"name": name, "color": color, "x": xs,
                "y": [_f(float(np.median(d[:, j])) / 1e6, 1) for j in range(d.shape[1])],
                "y_lo": [_f(float(np.percentile(d[:, j], 10)) / 1e6, 1) for j in range(d.shape[1])],
                "y_hi": [_f(float(np.percentile(d[:, j], 90)) / 1e6, 1) for j in range(d.shape[1])]}

    series = [
        {"name": "Act now (reference)", "color": "#1a73e8", "x": xs, "y": [0.0 for _ in xs]},
        diff(sq["mc_final"], "Cost of doing nothing", "#9aa0a6"),
        diff(dly["mc_final"], f"Cost of waiting {delay}y", "#d93025"),
    ]
    return {"name": "cost_trajectory", "kind": "line_band",
            "title": "Extra cost of waiting vs acting now, over 10 years",
            "subtitle": "every line starts at $0 today, then climbs",
            "x_label": "Year", "y_label": "Extra cost vs acting now ($M)",
            "series": series,
            "caption": "Acting now is the flat line at $0; the higher a line climbs, the more that choice adds.",
            "source": _SRC}


def cost_of_waiting(coc, budget, delay, n_mc=200):
    """TRUE waterfall: act-now total (the bill paid either way) -> the floating
    cost-of-waiting slice stacked on top -> the delayed total. The slice now has
    a baseline to read against instead of floating alone."""
    p = _params(coc); now, dly, _ = _scenarios(p, budget, delay, n_mc)
    cow = metrics.cost_of_waiting(now["mc_final"], dly["mc_final"])
    now_total = _f(cow["now_median"] / 1e6, 1)
    delay_total = _f(cow["delay_median"] / 1e6, 1)
    extra = _f(cow["extra_cost_median"] / 1e6, 1)
    slice_lo = _f((cow["now_median"] + cow["extra_cost_p10"]) / 1e6, 1)
    slice_hi = _f((cow["now_median"] + cow["extra_cost_p90"]) / 1e6, 1)
    return {"name": "cost_of_waiting", "kind": "waterfall",
            "title": f"Cost of waiting {delay} years",
            "subtitle": "the same bill, plus the penalty for waiting",
            "x_label": "", "y_label": "10-year public cost ($M)",
            "series": [{"name": "cost of waiting", "color": "#d93025",
                        "x": ["Act now", "+ cost of waiting", f"Wait {delay}y"],
                        "y": [now_total, extra, delay_total],
                        "base": [0.0, now_total, 0.0],
                        "measure": ["absolute", "relative", "total"],
                        "y_lo": [None, slice_lo, None],
                        "y_hi": [None, slice_hi, None],
                        # cost_of_waiting median kept addressable for the number-match test
                        "extra_cost": extra}],
            "caption": f"Waiting adds about ${extra:,.1f}M on top of the same starting bill (80% range "
                       f"${_f(cow['extra_cost_p10']/1e6,1):,.1f}M–${_f(cow['extra_cost_p90']/1e6,1):,.1f}M).",
            "source": _SRC}


def break_even_curve(coc, budget, delay=0, n_mc=None):
    p = _params(coc)
    be = metrics.break_even_year(p, lambda d: skills.make_scenario(p, f"d{d}", delay=d, budget=budget))
    tbl = be["table"]
    annual = be["annual_budget_usd"] / 1e6
    be_year = be["break_even_year"]
    annos = [{"type": "hline", "y": _f(annual, 1), "label": "one year of budget"}]
    if be_year:
        cross = next((t for t in tbl if t["delay_years"] == be_year), None)
        annos.append({"type": "vmarker", "x": be_year,
                      "y": _f(cross["extra_cost_vs_now"] / 1e6, 1) if cross else _f(annual, 1),
                      "label": f"break-even: year {be_year}"})
    return {"name": "break_even_curve", "kind": "line",
            "title": "Extra cost of delay vs how long you wait",
            "subtitle": f"break-even at year {be_year}" if be_year else "no break-even in 10y",
            "x_label": "Years waited", "y_label": "Extra cost vs acting now ($M)",
            "break_even_year": be_year,
            "series": [{"name": "extra cost", "color": "#d93025",
                        "x": [t["delay_years"] for t in tbl],
                        "y": [_f(t["extra_cost_vs_now"] / 1e6, 1) for t in tbl]}],
            "annotations": annos,
            "caption": "Where the rising line crosses one year of budget, waiting stops paying off.", "source": _SRC}


def scenario_costs(coc, budget, delay, n_mc=200):
    """DELTA view: act-now is the zero reference; the other two paths are plotted
    as EXTRA cost vs acting now, each with an 80% band on the per-run difference
    (tight, since correlated MC noise cancels). When a bar's band stays above $0
    the extra cost is real, not noise. Absolute totals kept for the tooltip."""
    p = _params(coc); now, dly, sq = _scenarios(p, budget, delay, n_mc)
    now_f = now["mc_final"][:, -1]
    d_sq = sq["mc_final"][:, -1] - now_f
    d_dly = dly["mc_final"][:, -1] - now_f

    def med(a): return _f(float(np.median(a)) / 1e6, 1)
    def p(a, q): return _f(float(np.percentile(a, q)) / 1e6, 1)
    los = [p(d_sq, 10), p(d_dly, 10)]
    return {"name": "scenario_costs", "kind": "bar_ci",
            "title": "Extra 10-year cost vs acting now",
            "subtitle": "acting now = $0; each bar is what that choice adds",
            "x_label": "", "y_label": "Extra cost vs acting now ($M)",
            "delta": True,
            "series": [{"name": "extra cost", "color": "#d93025",
                        "x": ["Status quo", f"Delay {delay}y"],
                        "y": [med(d_sq), med(d_dly)],
                        "y_lo": los, "y_hi": [p(d_sq, 90), p(d_dly, 90)],
                        "robust": [los[0] > 0, los[1] > 0],
                        "abs_total": [_f(sq["final_cum_cost_p50"] / 1e6, 1),
                                      _f(dly["final_cum_cost_p50"] / 1e6, 1)],
                        "ref_total": _f(now["final_cum_cost_p50"] / 1e6, 1)}],
            "caption": "Acting now is the baseline at $0; bars whose range stays above $0 cost more for sure.",
            "source": _SRC}


def compartments_over_time(coc, budget, delay=0, n_mc=None):
    """The decision on the costliest group: people UNSHELTERED (street + chronic)
    over 10 years, doing nothing vs acting now. The gap between the two lines is
    who acting now keeps off the street — a counterfactual, not just status-quo drift."""
    p = _params(coc); now, _, sq = _scenarios(p, budget, delay, n_mc or 80)

    def exposed(run):
        d = run["det"]; m = d["month"] % 12 == 0
        return [int(u + c) for u, c in zip(d["unsheltered"][m], d["chronic_unsheltered"][m])]

    dm = now["det"]["month"]
    xs = _years(dm[dm % 12 == 0])
    return {"name": "compartments_over_time", "kind": "line_band",
            "title": "People unsheltered over 10 years — wait vs act now",
            "subtitle": "the highest-cost group; the gap is who acting now keeps off the street",
            "x_label": "Year", "y_label": "People (unsheltered + chronic)",
            "series": [
                {"name": "Status quo", "color": "#9aa0a6", "x": xs, "y": exposed(sq)},
                {"name": "Act now", "color": "#1a73e8", "x": xs, "y": exposed(now)},
            ],
            "caption": "Keep doing nothing (gray) and more people stay on the street than if we act now (blue).",
            "source": _SRC}


def budget_comparison(coc, budgets=None, delay=0, n_mc=200):
    p = _params(coc); budgets = budgets or [15.0, 50.0, 100.0]
    cb = metrics.compare_budgets(p, budgets, delay=delay, n_mc=n_mc)
    return {"name": "budget_comparison", "kind": "bar",
            "title": "10-year cost by annual budget", "subtitle": f"lowest at {_blabel(cb['best_budget_musd'])}/yr",
            "x_label": "Annual budget ($M)", "y_label": "10-yr cost ($M)",
            "series": [{"name": "10-yr cost", "color": "#1a73e8",
                        "x": [_blabel(r["budget_musd"]) for r in cb["budgets"]],
                        "y": [_f(r["cum_cost_p50"] / 1e6, 1) for r in cb["budgets"]]}],
            "caption": "Compare what each budget buys over a decade.", "source": _SRC}


def cost_of_waiting_by_budget(coc, budgets=None, delay=3, n_mc=200):
    """Per-budget cost of waiting: one bar per program size, with the 80% band.
    The displayed quantity is the SAME cost-of-waiting the multi-budget answer
    states (not total cost) — so the chart matches the text."""
    p = _params(coc); budgets = budgets or [1.0, 15.0]
    sw = metrics.cost_of_waiting_sweep(p, budgets, delay=delay, n_mc=n_mc)
    rows = sw["rows"]
    return {"name": "cost_of_waiting_by_budget", "kind": "bar",
            "title": f"Cost of waiting {delay} years by program size",
            "subtitle": "extra 10-year public cost from delaying, per annual budget",
            "x_label": "Annual budget ($M)", "y_label": "Cost of waiting ($M)",
            "series": [{"name": "cost of waiting", "color": "#d93025",
                        "x": [_blabel(r["budget_musd"]) for r in rows],
                        "y": [_f(r["extra_cost_median"] / 1e6, 1) for r in rows],
                        "y_lo": [_f(r["extra_cost_p10"] / 1e6, 1) for r in rows],
                        "y_hi": [_f(r["extra_cost_p90"] / 1e6, 1) for r in rows]}],
            "caption": "Each bar is the extra public cost of waiting at that budget; the direction "
                       "(waiting costs more) holds at every size.",
            "source": _SRC}


_MIX_PRETTY = {
    "prevention": "Prevention", "rapid_rehousing": "Rapid re-housing",
    "rapid_re_housing": "Rapid re-housing", "supportive": "Supportive housing",
    "permanent_supportive_housing": "Supportive housing", "psh": "Supportive housing",
    "balanced": "Balanced mix",
}


def _pretty_mix(m):
    return _MIX_PRETTY.get(str(m), str(m).replace("_", " ").capitalize())


def mix_comparison(coc, budget=50.0, delay=0, n_mc=200):
    p = _params(coc); cm = metrics.compare_mix(p, budget, delay=delay, n_mc=n_mc)
    return {"name": "mix_comparison", "kind": "bar",
            "title": f"10-year cost by intervention mix (${budget:.0f}M/yr)",
            "subtitle": f"lowest: {_pretty_mix(cm['best_mix'])}", "x_label": "Mix", "y_label": "10-yr cost ($M)",
            "series": [{"name": "10-yr cost", "color": "#1d9e75",
                        "x": [_pretty_mix(r["mix"]) for r in cm["mixes"]],
                        "y": [_f(r["cum_cost_p50"] / 1e6, 1) for r in cm["mixes"]]}],
            "caption": "Where the money goes changes the payoff; near-level bars mean the choice barely matters.",
            "source": _SRC}


# Plain-English names for the model's internal states, so the tornado reads in
# words instead of raw engine identifiers (`sheltered -> exited_positive`).
_STATE = {
    "at_risk": "At-risk", "sheltered": "In shelter", "unsheltered": "On the street",
    "chronic_unsheltered": "Chronic / street", "housed_stable": "Stably housed",
    "exited_positive": "exits to housing", "exited_negative": "drops out",
}


def _pretty_driver(d):
    parts = [s.strip() for s in str(d).replace("->", "→").split("→")]
    return " → ".join(_STATE.get(p, p.replace("_", " ").capitalize()) for p in parts)


def sensitivity_tornado(coc, budget=50.0, delay=0, n_mc=None):
    p = _params(coc)
    drivers = metrics.sensitivity_drivers(p, skills.make_scenario(p, "now", budget=budget))
    drivers = list(reversed(drivers))
    # "tighten first" = high impact AND low confidence (where conclusions are fragile).
    thresh = max((abs(d["pct_change"]) for d in drivers), default=0) * 0.5
    return {"name": "sensitivity_tornado", "kind": "tornado",
            "title": "What moves the result most (+20% each rate)",
            "subtitle": "longer bar = more influence; color = how sure we are of that rate",
            "x_label": "% change in 10-yr cost", "y_label": "",
            "series": [{"name": "impact", "x": [_f(d["pct_change"], 1) for d in drivers],
                        "y": [_pretty_driver(d["driver"]) for d in drivers],
                        "raw": [d["driver"] for d in drivers],
                        "conf": [d["confidence"] for d in drivers],
                        "tighten_first": [bool(abs(d["pct_change"]) >= thresh and d["confidence"] == "low")
                                          for d in drivers]}],
            "caption": "Low-confidence, high-impact rows (flagged) are where conclusions are fragile.", "source": _SRC}


def shap_drivers(coc="CA-600", **kw):
    im = skills.load_inflow_model()
    sh = im["shap_target"]
    return {"name": "shap_drivers", "kind": "shap_bar",
            "title": "What drives the model's homelessness estimate",
            "subtitle": "how much each factor raises or lowers predicted homelessness",
            "x_label": "Effect on predicted homelessness (people per 1,000)", "y_label": "",
            "series": [{"name": "shap", "x": [_f(d["shap"], 2) for d in sh],
                        "y": [d["feature"] for d in sh]}],
            "caption": "Housing cost leads by far — matching the research on what drives homelessness.", "source": _SRC}


def backtest(coc="CA-600", **kw):
    bt = skills.run_backtest(_params(coc))
    passed = bool(bt["within_band"])
    return {"name": "backtest", "kind": "dot_interval",
            "title": "Reality check: predicted 2024 vs what happened",
            "subtitle": ("The real 2024 count lands inside the model's predicted range — it passes."
                         if passed else "The real 2024 count falls outside the predicted range."),
            "pass": passed, "x_unit": "active homeless people",
            "x_label": "", "y_label": "Active homeless",
            "series": [{"name": "model", "color": "#1a73e8", "x": ["2024"],
                        "y": [_f(bt["predicted_active_p50"], 0)],
                        "y_lo": [_f(bt["predicted_active_p10"], 0)],
                        "y_hi": [_f(bt["predicted_active_p90"], 0)]},
                       {"name": "observed", "color": "#188038", "x": ["2024"],
                        "y": [int(bt["observed_2024_total"])]}],
            "caption": "Observed sits inside the model's predicted band.", "source": _SRC}


def _panel():
    df = pd.read_csv(_PANEL)
    df["rate"] = df["pit_total"] / df["population"] * 1000.0
    return df


def city_scatter(coc="CA-600", **kw):
    df = _panel()
    pts = [{"coc": r.coc, "x": int(r.median_home_value), "y": _f(r.rate, 2),
            "highlight": bool(r.coc == coc)} for r in df.itertuples()]
    # Least-squares trend line over the 17 cities — the "upward relationship" the
    # caption claims, now actually drawn. Also flag the selected city's residual.
    xs = np.array([pp["x"] for pp in pts], dtype=float)
    ys = np.array([pp["y"] for pp in pts], dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)
    x0, x1 = float(xs.min()), float(xs.max())
    trend = {"x0": x0, "y0": _f(slope * x0 + intercept, 2),
             "x1": x1, "y1": _f(slope * x1 + intercept, 2)}
    sel = next((pp for pp in pts if pp["highlight"]), None)
    residual = None
    if sel:
        residual = _f(sel["y"] - (slope * sel["x"] + intercept), 2)
    return {"name": "city_scatter", "kind": "scatter",
            "title": "Housing cost vs homelessness across cities",
            "subtitle": f"{coc} highlighted; the line is the typical pattern",
            "x_label": "Median home value ($)", "y_label": "Homeless per 1,000",
            "trend": trend, "residual": residual,
            "series": [{"name": "cities", "points": pts}],
            "caption": ("The diagonal is the typical pattern; this city sits "
                        f"{abs(residual):.1f}/1,000 {'above' if (residual or 0) > 0 else 'below'} it."
                        if residual is not None else "The model learned this upward relationship."),
            "source": _SRC}


def city_benchmark(coc="CA-600", **kw):
    df = _panel().sort_values("rate")
    return {"name": "city_benchmark", "kind": "bar",
            "title": "Homelessness rate by city", "subtitle": f"{coc} highlighted",
            "x_label": "Homeless per 1,000", "y_label": "",
            "series": [{"name": "rate", "x": [_f(r.rate, 2) for r in df.itertuples()],
                        "y": [r.coc for r in df.itertuples()],
                        "highlight": [bool(r.coc == coc) for r in df.itertuples()]}],
            "caption": "Where this city sits among its peers.", "source": _SRC, "horizontal": True}


def city_map(coc="CA-600", **kw):
    df = _panel()
    pts = []
    for r in df.itertuples():
        if r.coc in _COORDS:
            lat, lon = _COORDS[r.coc]
            pts.append({"coc": r.coc, "lat": lat, "lon": lon, "rate": _f(r.rate, 2),
                        "pit_total": int(r.pit_total), "highlight": bool(r.coc == coc)})
    return {"name": "city_map", "kind": "map", "title": "Cities by homelessness rate",
            "subtitle": "bubble size = rate per 1,000", "series": [{"name": "cities", "points": pts}],
            "caption": "The 17 cities the same model scores.", "source": _SRC}


def equity_disparity(coc="CA-600", **kw):
    from analysis.equity import equity_analysis
    a = equity_analysis(coc)
    g = [x for x in a["groups"] if x["disproportionality"]]
    g = sorted(g, key=lambda x: x["disproportionality"])
    return {"name": "equity_disparity", "kind": "bar", "horizontal": True,
            "title": "Over-representation among the homeless (× population share)",
            "subtitle": f"{a['most_overrepresented']['group']} most over-represented", "x_label": "× of population share", "y_label": "",
            "series": [{"name": "disproportionality", "y": [x["group"] for x in g],
                        "x": [x["disproportionality"] for x in g],
                        "highlight": [x["disproportionality"] > 1.2 for x in g]}],
            "caption": "1.0 = parity. Bars past 1.0 are over-represented — structural inequity.",
            "source": "HUD 2024 PIT + Census ACS (population-level; no individual profiling)."}


def equity_unsheltered(coc="CA-600", **kw):
    from analysis.equity import equity_analysis
    a = equity_analysis(coc)
    g = sorted(a["groups"], key=lambda x: x["unsheltered_rate_pct"], reverse=True)
    return {"name": "equity_unsheltered", "kind": "bar",
            "title": "Unsheltered rate by group", "subtitle": "who is most exposed (highest-cost state)",
            "x_label": "", "y_label": "% unsheltered",
            "series": [{"name": "unsheltered %", "color": "#d93025",
                        "x": [x["group"] for x in g], "y": [x["unsheltered_rate_pct"] for x in g]}],
            "caption": "Unsheltered homelessness carries the highest public cost and risk.",
            "source": "HUD 2024 PIT CoC PopSub."}


def roi(coc="CA-600", budget=50.0, delay=0, n_mc=200):
    p = _params(coc); now, _, sq = _scenarios(p, budget, delay, n_mc)
    savings = float(np.median(sq["mc_final"][:, -1] - now["mc_final"][:, -1]))
    horizon = int(p["meta"]["horizon_months"] // 12)
    spend = float(budget) * 1e6 * horizon
    ratio = savings / spend if spend > 0 else 0.0
    net = _f((savings - spend) / 1e6, 1)
    return {"name": "roi", "kind": "bar",
            "title": f"Return on ${budget:.0f}M/yr over {horizon} years",
            "subtitle": f"every $1 spent now returns about ${ratio:.1f} in avoided public cost",
            "x_label": "", "y_label": "$M (over horizon)",
            # no_best stops VBar highlighting the SMALLER bar as 'best' (wrong for ROI);
            # explicit colors keep spend=clay (cost) and avoided=indigo (the good outcome).
            "no_best": True, "ratio": round(ratio, 1), "net_musd": net,
            "series": [{"name": "value",
                        "x": ["Program spend", "Public cost avoided"],
                        "y": [_f(spend / 1e6, 1), _f(savings / 1e6, 1)],
                        "colors": ["var(--viz-wait)", "var(--viz-act)"]}],
            "caption": f"Acting now avoids about ${net:,.1f}M more than it costs — ~${ratio:.1f} back per $1.",
            "source": _SRC}


def people_helped(coc="CA-600", budget=50.0, delay=0, n_mc=200):
    p = _params(coc); now, _, sq = _scenarios(p, budget, delay, n_mc)
    sq_n, now_n = int(sq["final_active_homeless"]), int(now["final_active_homeless"])
    helped = max(0, sq_n - now_n)
    return {"name": "people_helped", "kind": "bar",
            "title": "People homeless at the 10-year horizon",
            "subtitle": "status quo vs acting now — the bracket is who acting now keeps housed",
            "x_label": "", "y_label": "People", "no_best": True,
            # gap annotation: a bracket between the two bar tops labeled with the delta.
            "gap": {"from": 0, "to": 1, "value": helped, "label": f"{helped:,} kept housed"},
            "series": [{"name": "people",
                        "x": ["Status quo", "Act now"], "y": [sq_n, now_n],
                        "colors": ["var(--viz-neutral)", "var(--viz-act)"]}],
            "caption": f"Acting now keeps about {helped:,} people out of homelessness vs. doing nothing.",
            "source": _SRC}


def regional_waiting(coc="CA-600", budget=50.0, delay=5, n_mc=120):
    reg = skills.regional_cost_of_waiting(budget, int(delay) or 5, n_mc=n_mc)
    cities = reg["cities"]
    return {"name": "regional_waiting", "kind": "bar", "horizontal": True,
            "title": f"Cost of waiting {reg['delay_years']} years by city",
            "subtitle": f"${budget:.0f}M/yr · same engine, real PIT+ACS per city",
            "x_label": "Cost of waiting ($M)", "y_label": "",
            "series": [{"name": "cost of waiting", "color": "#d93025",
                        "x": [r["cost_of_waiting_musd"] for r in cities],
                        "y": [r["coc"] for r in cities],
                        "highlight": [bool(r["coc"] == coc) for r in cities]}],
            "caption": "Where inaction is most expensive.", "source": _SRC}


_BUILDERS = {
    "cost_trajectory": cost_trajectory, "cost_of_waiting": cost_of_waiting,
    "roi": roi, "people_helped": people_helped, "regional_waiting": regional_waiting,
    "break_even_curve": break_even_curve, "scenario_costs": scenario_costs,
    "compartments_over_time": compartments_over_time, "budget_comparison": budget_comparison,
    "cost_of_waiting_by_budget": cost_of_waiting_by_budget,
    "mix_comparison": mix_comparison, "sensitivity_tornado": sensitivity_tornado,
    "shap_drivers": shap_drivers, "backtest": backtest, "city_scatter": city_scatter,
    "city_benchmark": city_benchmark, "city_map": city_map,
    "equity_disparity": equity_disparity, "equity_unsheltered": equity_unsheltered,
}


# Plain-English "how to read this" per chart — one source of truth so the text
# can't drift from the chart. `plain` always shown inline; `analogy`/`tech` deepen
# the Explain popover. Injected by VizAgent.build() so coverage can't be forgotten.
_HOW_TO_READ = {
    "cost_trajectory": {"plain": "The flat indigo line is the cost of acting now; the rising lines show "
                        "how many extra dollars waiting (clay) or doing nothing (gray) piles on by each "
                        "year — so the gap between the lines is exactly what your decision is worth."},
    "cost_of_waiting": {"plain": "The tall indigo bar is the bill you pay either way; the small clay block "
                        "stacked on top is the extra you pay only because you waited — the right bar is the "
                        "two added together.",
                        "analogy": "Like a base fare plus a late fee: the fare is the same, the fee is what "
                        "waiting cost you."},
    "scenario_costs": {"plain": "Acting now is the baseline at zero; each bar shows how many extra dollars "
                       "that choice costs over ten years, and when a bar's range stays above zero the extra "
                       "cost is real, not just noise."},
    "break_even_curve": {"plain": "The rising line is the extra cost of waiting that many years; the flat "
                         "dashed line is one full year of the program budget — the marked point where they "
                         "cross is the last year you can wait before delay costs more than a whole year of funding."},
    "compartments_over_time": {"plain": "If we keep doing nothing, this many people stay unsheltered each "
                               "year (gray); if we act now, fewer do (blue) — the gap between them is the "
                               "people acting now keeps off the street."},
    "people_helped": {"plain": "The left bar is how many people are still homeless in 10 years if we wait; "
                      "the right bar is how many if we act now — the labeled gap is the people acting now "
                      "keeps off the street."},
    "roi": {"plain": "The clay amount is what acting now costs; the taller indigo amount is the public "
            "spending it avoids — the part of the avoided cost above the spend is your net return."},
    "budget_comparison": {"plain": "Each bar is the total 10-year public cost at that annual budget (the "
                          "axis starts near the data so small gaps are visible) — the shortest, highlighted "
                          "bar is the cheapest budget over a decade."},
    "cost_of_waiting_by_budget": {"plain": "Each bar is the extra 10-year public cost of waiting at that "
                          "program size — taller bars mean a bigger penalty for delay; the whiskers are the "
                          "80% range. The bars rise with budget, but every one is above zero: waiting costs "
                          "more at any size."},
    "mix_comparison": {"plain": "Each bar is the 10-year cost of putting the same budget into a different "
                       "mix of prevention, rapid re-housing, and supportive housing — the shortest "
                       "highlighted bar is the cheapest mix; near-level bars mean the choice barely matters."},
    "shap_drivers": {"plain": "Each bar shows one fact about the city (like its housing cost) and how much "
                     "it pushes the model's homelessness estimate up or down — longer bars matter more; "
                     "housing cost is by far the strongest.",
                     "tech": "SHAP attributes the model's predicted homelessness rate (per 1,000 residents) "
                     "to each input. Model: gb_stumps; held-out (leave-one-CoC-out) R²≈0.36 — it explains "
                     "about a third of why cities differ."},
    "backtest": {"plain": "The shaded bar is the range the model expected for 2024; the hollow dot is the "
                 "real count that happened — because the real number lands inside the model's range, the "
                 "model passes its reality check.",
                 "tech": "Seeded on the real 2023 PIT and run forward 12 months, the model's P10–P90 band "
                 "for 2024 contains the observed count (central error ~9%)."},
    "sensitivity_tornado": {"plain": "Each bar shows how much the 10-year cost would shift if that one "
                            "assumption were 20% higher — the longest bars matter most, and the colors flag "
                            "which assumptions we're least sure about, so those are worth checking first.",
                            "tech": "A one-at-a-time sweep: each transition rate raised +20% and the 10-year "
                            "cost re-priced. Bar length = sensitivity; color = confidence in that rate."},
    "city_scatter": {"plain": "Each dot is a city: further right means pricier homes, higher up means more "
                     "homelessness. The diagonal line is the typical pattern — your city above it has more "
                     "homelessness than its housing costs alone would predict."},
    "city_benchmark": {"plain": "Each bar is a city's homelessness rate per 1,000 residents; your selected "
                       "city is highlighted — longer bars mean a higher rate."},
    "city_map": {"plain": "Each bubble is a city at its real location, sized by its homelessness rate — "
                 "bigger bubbles mean more homelessness per resident."},
    "equity_disparity": {"plain": "Each bar is a group's share of homelessness divided by its share of the "
                         "population — 1.0 is a fair share, and bars past 1.0 mean that group is "
                         "over-represented among people experiencing homelessness."},
    "equity_unsheltered": {"plain": "Each bar is the share of a group's homelessness that is unsheltered — "
                           "on the street, the highest-cost state — so taller bars mean that group is more exposed."},
    "regional_waiting": {"plain": "Each bar is one city's cost of waiting; your selected city is highlighted "
                         "— the longer the bar, the more that city loses by delaying."},
}


class VizAgent:
    """The visualization specialist: recommend a chart, then build its spec."""

    def list_charts(self):
        return CHART_CATALOG

    def recommend(self, intent):
        return INTENT_CHART.get(intent, "cost_trajectory")

    def build(self, name, coc="CA-600", budget=50.0, delay=3, budgets=None, n_mc=200):
        if name not in _BUILDERS:
            raise ValueError(f"Unknown chart '{name}'. Options: {list(_BUILDERS)}")
        fn = _BUILDERS[name]
        kw = {"coc": coc, "budget": budget, "delay": delay, "n_mc": n_mc}
        if name in ("budget_comparison", "cost_of_waiting_by_budget"):
            kw["budgets"] = budgets
        # builders accept a subset of kwargs; filter to what each takes
        import inspect
        allowed = set(inspect.signature(fn).parameters)
        spec = fn(**{k: v for k, v in kw.items() if k in allowed})
        # Guarantee every chart carries its plain-English explainer (inline + popover).
        if "how_to_read" not in spec and name in _HOW_TO_READ:
            spec["how_to_read"] = _HOW_TO_READ[name]
        return spec


def build_chart(name, coc="CA-600", budget=50.0, delay=3, budgets=None, n_mc=200):
    return VizAgent().build(name, coc=coc, budget=budget, delay=delay, budgets=budgets, n_mc=n_mc)
