"""JSON-safe payload builders for the API — pure functions, no web framework.

Kept separate from main.py so the data logic is unit-testable without FastAPI.
Every payload comes from the SAME skills the agent uses, so the web app, the
Streamlit app, and the agent never disagree on a number.
"""
import os

import numpy as np
import pandas as pd

from agent import skills
from agent.orchestrator import WaitCostAgent
from analysis import metrics
from model.states import ACTIVE_HOMELESS
from model.coc_registry import available_cocs, build_params_for_coc

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS_PATH = os.path.join(REPO, "config", "params.yaml")
MODEL_PATH = os.path.join(REPO, "model", "inflow_model.json")
PANEL_PATH = os.path.join(REPO, "data", "coc_panel.csv")

# Approximate city centroids for the 15 training CoCs (for the map).
COC_COORDS = {
    "CA-600": (34.05, -118.24), "CA-601": (32.72, -117.16), "CA-501": (37.77, -122.42),
    "WA-500": (47.61, -122.33), "AZ-502": (33.45, -112.07), "CA-500": (37.34, -121.89),
    "OR-501": (45.52, -122.68), "NV-500": (36.17, -115.14), "NY-600": (40.71, -74.01),
    "DC-500": (38.90, -77.04), "MN-500": (44.98, -93.27), "TN-502": (35.96, -83.92),
    "FL-600": (25.76, -80.19), "PA-500": (39.95, -75.16), "IL-510": (41.88, -87.63),
    "CA-503": (38.58, -121.49), "AZ-501": (32.22, -110.97),
}


def jsonable(o):
    """Recursively convert numpy types to plain Python so FastAPI can serialize."""
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def _params(coc=None):
    if coc and coc != "CA-600":
        return build_params_for_coc(coc)
    return skills.fetch_hud_data(PARAMS_PATH)


def cocs_payload():
    """The cities the engine can run (the trained panel)."""
    return jsonable(available_cocs())


def tools_payload():
    """The agent's function-calling catalog (capabilities + counts)."""
    from agent import tools
    return jsonable({**tools.registry_summary(), "capabilities": tools.list_capabilities()})


def context_payload(coc="CA-600"):
    """Retrieve essential US public indicators for a city (decision context)."""
    return jsonable(skills.retrieve_us_context(coc))


def equity_payload(coc="CA-600"):
    """Population-level racial-disparity analysis for a city (decision equity)."""
    from analysis.equity import equity_analysis
    return jsonable(equity_analysis(coc))


def city_brief_payload(coc="CA-600"):
    """Grounded city homelessness brief from the THIRD agent (CityBriefAgent).
    Qualitative context + citations — explicitly NOT the calibrated cost model."""
    from agent.city_brief import CityBriefAgent
    agent = CityBriefAgent(memory_path=MEMORY_PATH)
    return jsonable(agent.brief(coc))


def city_sources_payload(coc="CA-600"):
    """The raw curated registry entry for a CoC plus the national frameworks."""
    import json as _json
    path = os.path.join(REPO, "data", "city_sources.json")
    with open(path) as f:
        reg = _json.load(f)
    entry = next((c for c in reg.get("cities", []) if c.get("coc") == coc), None)
    return jsonable({"coc": coc, "entry": entry,
                     "national_frameworks": reg.get("national_frameworks", [])})


def charts_payload():
    """The visualization agent's chart catalog (what to draw, and when)."""
    from analysis.viz import CHART_CATALOG
    return jsonable(CHART_CATALOG)


def chart_payload(name, coc="CA-600", budget=50.0, delay=3, n_mc=None, budgets=None):
    """Build one chart spec (render-ready) from real engine output.

    n_mc defaults to the city's `monte_carlo_runs` so the chart runs the SAME
    seeded Monte Carlo as the agent's answer — making the chart's numbers identical
    to the text (the waterfall's $X == the headline $X). The regional ranking keeps
    its lighter count (matching skills.regional_cost_of_waiting) for responsiveness.
    """
    from analysis.viz import build_chart
    if n_mc is None:
        n_mc = 120 if name == "regional_waiting" else int(_params(coc)["meta"].get("monte_carlo_runs", 200))
    return jsonable(build_chart(name, coc=coc, budget=budget, delay=delay, n_mc=n_mc, budgets=budgets))


def _acs_release(coc="CA-600"):
    """ACS provenance/vintage straight from the committed panel (e.g. 'ACS 2024 1-yr (API)')
    so the frontend surfaces it instead of hard-coding the chip text."""
    df = pd.read_csv(PANEL_PATH)
    sel = df[df["coc"] == coc]
    return str(sel.iloc[0]["acs_release"]) if not sel.empty else "ACS 2024 1-yr (API)"


MANIFEST_PATH = os.path.join(REPO, "data_sources", "SOURCES_MANIFEST.md")


def _clean_md(s):
    """Strip the bits of Markdown we don't want in a popover (bold, code ticks)."""
    return s.replace("**", "").replace("`", "").strip()


def _parse_manifest_sources():
    """Parse the primary-sources table in data_sources/SOURCES_MANIFEST.md into
    {row_number: {source, publisher, vintage, used_for, link}}. The provenance map
    is sourced from here so we never hard-code new facts — the manifest is the
    single source of truth for what every number is and where it came from."""
    rows = {}
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return rows
    for ln in lines:
        if not ln.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 6 or not cells[0].isdigit():
            continue   # skip header + separator rows
        rows[int(cells[0])] = {
            "source": _clean_md(cells[1]),
            "publisher": _clean_md(cells[2]),
            "vintage": _clean_md(cells[3]),
            "used_for": _clean_md(cells[4]),
            "link": _clean_md(cells[5]),
        }
    return rows


def provenance_payload():
    """Feature ① — where every on-screen number comes from, keyed by metric family.

    Each family carries {label, source, vintage, note} (+ publisher/link when known).
    Real-data families are pulled from the SOURCES_MANIFEST.md table; engine outputs
    (cost-of-waiting, scenario bands) are labelled as ranges, not point estimates.
    This endpoint *describes* numbers — it never computes or alters one."""
    m = _parse_manifest_sources()

    def fam(label, row, note, **extra):
        r = m.get(row, {})
        return {"label": label,
                "source": r.get("source", ""),
                "publisher": r.get("publisher", ""),
                "vintage": r.get("vintage", ""),
                "link": r.get("link", ""),
                "note": note, **extra}

    RANGE_NOTE = "Engine output — 80% Monte-Carlo range, not a point estimate."
    out = {
        "homeless_counts": fam(
            "Homeless counts", 1,
            "Point-in-Time street + shelter census; this is a count, reported as a range only in aggregate."),
        "economic_features": fam(
            "Economic features", 2,
            "Reproducible from the Census API (scripts/fetch_acs.py); verified 0/119 values differed ≥5%."),
        "flow_rates": fam(
            "System flow rates", 3,
            "HMIS-reported annual rates converted to monthly transition hazards; calibrated for CA-600."),
        "costs": fam(
            "Per-person costs", 5,
            "Published per-person public-cost figures in 2024 dollars; each tagged with source + confidence."),
        "equity": fam(
            "Equity / disparity", 4,
            "Population-level over-representation vs. ACS population shares — never individual-level."),
        "cost_of_waiting": {
            "label": "Cost of waiting", "source": "WaitCost engine (system dynamics + Monte Carlo)",
            "publisher": "WaitCost", "vintage": "Recomputed per request", "link": "",
            "note": RANGE_NOTE},
        "scenario": {
            "label": "Scenario bands", "source": "WaitCost engine (system dynamics + Monte Carlo)",
            "publisher": "WaitCost", "vintage": "Recomputed per request", "link": "",
            "note": RANGE_NOTE},
        "model": {
            "label": "Learned model", "source": "WaitCost inflow predictor (gradient-boosted stumps on ACS features)",
            "publisher": "WaitCost", "vintage": "Refit on the API-sourced panel", "link": "",
            "note": "Validated leave-one-CoC-out — held-out fit, not memorized; cross-checked vs HUD SPM."},
    }
    return jsonable(out)


def params_payload():
    p = _params()
    return jsonable({"coc": p["meta"]["coc"], "data_vintage": p["meta"]["data_vintage"],
                     "acs_release": _acs_release(),
                     "horizon_years": p["meta"]["horizon_months"] // 12,
                     "discount_annual": p["meta"]["discount_annual"],
                     "default_budget_musd": p["meta"]["default_budget_musd"]})


_COMP_GROUP = {"chronic_unsheltered": "Chronically unsheltered", "unsheltered": "Unsheltered",
               "sheltered": "Sheltered", "at_risk": "At-risk", "housed_stable": "Housed (stable)",
               "exited_positive": "Exited", "program_spend": "Program spend (your budget)"}


def _composition_payload(params, scenario, total_usd, baseline_usd):
    """Where a scenario's 10-yr cost goes. The engine's cumulative cost is
    `public homelessness cost + program spend` (simulate.py). So we show TWO kinds
    of slice: the public cost split by homeless group (the cost of homelessness
    itself), PLUS a distinct **program spend** slice (the money you chose to spend).
    Without the spend slice, the per-group figures had to be inflated to absorb the
    spend — hiding it and making an over-scaled budget look like it cost that much
    on homelessness. `baseline_usd` (do-nothing public cost) drives the saves bar."""
    comp = metrics.cost_composition(params, scenario)        # deterministic public cost by group
    pub_total = comp["total"] or 1.0
    # Program spend over the horizon (the donut's scenario is act-now → active every
    # month, so spend = annual budget × horizon years). This is the slice you control.
    horizon_years = params["meta"]["horizon_months"] / 12.0
    spend_usd = max(0.0, float(getattr(scenario, "annual_budget_musd", 0.0)) * 1e6 * horizon_years)
    # total_usd (the on-screen MC P50) = public + spend; split it back the same way,
    # scaling the public-by-group split to the public portion (≈1× now, not ~2×).
    public_display = max(total_usd - spend_usd, 0.0)
    pscale = public_display / pub_total
    rows = [(k, v * pscale) for k, v in comp["by_state"].items() if v > 0]
    if spend_usd > 0:
        rows.append(("program_spend", spend_usd))
    rows.sort(key=lambda kv: -kv[1])
    denom = total_usd or 1.0
    groups = [{"key": k, "label": _COMP_GROUP.get(k, k),
               "cost_musd": val / 1e6, "pct": val / denom * 100} for k, val in rows]
    return {"total_musd": total_usd / 1e6, "baseline_musd": baseline_usd / 1e6,
            "saves_vs_nothing_musd": (baseline_usd - total_usd) / 1e6,
            "spend_musd": spend_usd / 1e6, "groups": groups}


def scenario_payload(budget=50.0, delay=3, n_mc=200, mix=None, coc=None):
    p = _params(coc)
    now_sc = skills.make_scenario(p, "Act now", delay=0, budget=budget, mix=mix)
    now = skills.run_simulation(p, now_sc, n_mc)
    dly = skills.run_simulation(p, skills.make_scenario(p, f"Delay {delay}y", delay=delay, budget=budget, mix=mix), n_mc)
    sq = skills.run_simulation(p, skills.make_scenario(p, "Status quo", budget=0.0), n_mc)
    cow = metrics.cost_of_waiting(now["mc_final"], dly["mc_final"])

    def band(r):                         # downsample to yearly points for a small payload
        b = r["bands"]; yr = b["month"] % 12 == 0
        return {"year": (b["month"][yr] / 12).tolist(),
                "p10": (b["p10"][yr] / 1e6).round(1).tolist(),
                "p50": (b["p50"][yr] / 1e6).round(1).tolist(),
                "p90": (b["p90"][yr] / 1e6).round(1).tolist()}

    def summ(r):
        return {"scenario": r["scenario"], "cum_cost_p50_musd": r["final_cum_cost_p50"] / 1e6,
                "cum_cost_p10_musd": r["final_cum_cost_p10"] / 1e6,
                "cum_cost_p90_musd": r["final_cum_cost_p90"] / 1e6,
                "active_homeless": r["final_active_homeless"]}

    # Divergence vs acting now: how much MORE each scenario costs than act-now, by
    # year. Computed from the PAIRED Monte-Carlo draws (same seed across scenarios),
    # so the bands are real paired differences — this is what makes the decision
    # visible when the absolute trajectories overlap.
    now_arr = now["mc_final"]
    yr_idx = [m for m in range(now_arr.shape[1]) if m % 12 == 0]

    def div_band(arr):
        d = arr[:, yr_idx] - now_arr[:, yr_idx]
        return {"p10": (np.percentile(d, 10, axis=0) / 1e6).round(1).tolist(),
                "p50": (np.percentile(d, 50, axis=0) / 1e6).round(1).tolist(),
                "p90": (np.percentile(d, 90, axis=0) / 1e6).round(1).tolist()}

    divergence = {
        "years": [m // 12 for m in yr_idx],
        "status_quo": div_band(sq["mc_final"]),   # do-nothing minus act-now = savings forgone
        "delay": div_band(dly["mc_final"]),        # delay minus act-now = cost of waiting
    }

    return jsonable({
        "budget_musd": budget, "delay_years": delay,
        "scenarios": [summ(sq), summ(now), summ(dly)],
        "bands": {"status_quo": band(sq), "act_now": band(now), "delay": band(dly)},
        "divergence": divergence,
        "cost_of_waiting_musd": {"p50": cow["extra_cost_median"] / 1e6,
                                 "p10": cow["extra_cost_p10"] / 1e6,
                                 "p90": cow["extra_cost_p90"] / 1e6},
        "composition": _composition_payload(p, now_sc, float(now["final_cum_cost_p50"]),
                                            float(sq["final_cum_cost_p50"])),
    })


def effect_band_payload(budget=50.0, delay=3):
    eb = metrics.cost_of_waiting_effect_band(_params(), {"budget_musd": budget, "delay_years": delay})
    return jsonable({"delay_years": delay, "budget_musd": budget,
                     "cow_lo_musd": eb["cow_at_lo"] / 1e6, "cow_base_musd": eb["cow_base"] / 1e6,
                     "cow_hi_musd": eb["cow_at_hi"] / 1e6, "effect_lo": eb["effect_lo"], "effect_hi": eb["effect_hi"]})


# Writable locations. Default to the repo, but honor env overrides so a read-only
# host (e.g. Vercel serverless, where only /tmp is writable) can redirect them.
OUT_DIR = os.environ.get("WAITCOST_OUT_DIR", os.path.join(REPO, "outputs"))
MEMORY_PATH = os.environ.get("WAITCOST_MEMORY_PATH", os.path.join(REPO, "MEMORY.md"))


def make_agent(coc=None):
    """Construct a WaitCostAgent for a CoC (used by /ask, /ask/stream, exports)."""
    override = build_params_for_coc(coc) if coc and coc != "CA-600" else None
    return WaitCostAgent(PARAMS_PATH, memory_path=MEMORY_PATH,
                         max_auto_tier=1, params=override)


def run_agent(question, approve_allocation=False, coc=None, on_step=None):
    """Run the full agent loop and return the raw (not-yet-jsonable) result dict."""
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
    except OSError:
        pass  # read-only fs — brief-file artifacts are best-effort; the payload is self-contained
    agent = make_agent(coc)
    return agent.answer(question, out_dir=OUT_DIR,
                        approve_allocation=approve_allocation, on_step=on_step)


def ask_payload(question, approve_allocation=False, coc=None):
    return jsonable(run_agent(question, approve_allocation=approve_allocation, coc=coc))


def compare_cities_payload(question, budget_musd, delay_years, coc_a, coc_b):
    """Feature ④ — run the SAME question across two cities and return both
    results plus a population-level numeric delta (a vs b)."""
    q = question or f"What if we wait {int(delay_years)} years on a ${budget_musd:.0f}M program?"
    a = run_agent(q, coc=coc_a)
    b = run_agent(q, coc=coc_b)

    def cow_musd(res):
        c = (res.get("comparison") or {}).get("cost_of_waiting") or {}
        v = c.get("extra_cost_median")
        return None if v is None else v / 1e6

    def rate_per_1k(coc):
        ctx = skills.retrieve_us_context(coc)
        return ctx["indicators"]["homeless_rate_per_1k"]

    cow_a, cow_b = cow_musd(a), cow_musd(b)
    delta = {
        "cost_of_waiting_musd": (None if cow_a is None or cow_b is None
                                 else round(cow_a - cow_b, 1)),
        "rate_per_1k": round(rate_per_1k(coc_a) - rate_per_1k(coc_b), 2),
    }
    return jsonable({"question": q, "budget_musd": budget_musd, "delay_years": delay_years,
                     "coc_a": coc_a, "coc_b": coc_b, "a": a, "b": b, "delta": delta})


def model_payload():
    im = skills.load_inflow_model(MODEL_PATH)
    return jsonable(im) if im else {"error": "model not trained — run scripts/train_inflow.py"}


def backtest_payload():
    return jsonable(skills.run_backtest(_params()))


def coc_points():
    """The 15 training CoCs as map points: location + homelessness + housing cost."""
    df = pd.read_csv(PANEL_PATH)
    df["rate_per_1k"] = df["pit_total"] / df["population"] * 1000.0
    pts = []
    for _, r in df.iterrows():
        lat_lon = COC_COORDS.get(r["coc"])
        if not lat_lon:
            continue
        pts.append({"coc": r["coc"], "name": r["coc_name"], "lat": lat_lon[0], "lon": lat_lon[1],
                    "pit_total": int(r["pit_total"]), "population": int(r["population"]),
                    "rate_per_1k": round(float(r["rate_per_1k"]), 2),
                    "median_home_value": int(r["median_home_value"]),
                    "highlight": bool(r["coc"] == "CA-600")})
    return jsonable(pts)


def geo_payload():
    """Same data as GeoJSON, so a Leaflet GeoJSON layer can render it directly.

    Points only for now; real CoC boundary polygons come from HUD's open-data GIS
    (hudgis-hud.opendata.arcgis.com) and can be added as Polygon features later.
    """
    feats = [{"type": "Feature",
              "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
              "properties": {k: v for k, v in p.items() if k not in ("lat", "lon")}}
             for p in coc_points()]
    return {"type": "FeatureCollection", "features": feats}
