"""WaitCost dashboard (Streamlit) — multi-city, the complete demoable solution.

    streamlit run app/dashboard.py

Same engine + same trained model the agent uses (every number traceable). A city
selector reuses the cross-CoC model for any of the 15 trained cities; CA-600
(Los Angeles) is the fully SPM-calibrated, backtested reference.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from agent import skills, planner  # noqa: E402
from agent.orchestrator import WaitCostAgent, TierViolation  # noqa: E402
from analysis import metrics  # noqa: E402
from model.states import ACTIVE_HOMELESS  # noqa: E402
from model.coc_registry import available_cocs, build_params_for_coc  # noqa: E402
from analysis import viz  # noqa: E402

PARAMS_PATH = "config/params.yaml"
st.set_page_config(page_title="WaitCost — Cost of Doing Nothing", layout="wide")


def usd(x):
    return f"${x/1e6:,.1f}M"


def render_spec(spec):
    """Draw any chart spec from the visualization agent with Plotly (switch on kind)."""
    k = spec["kind"]; fig = go.Figure()
    if k == "line_band":
        for s in spec["series"]:
            fig.add_trace(go.Scatter(x=s["x"], y=s["y_hi"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=s["x"], y=s["y_lo"], fill="tonexty", line=dict(width=0), opacity=0.15, showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=s["x"], y=s["y"], line=dict(color=s.get("color"), width=3), name=s["name"]))
    elif k in ("bar", "bar_ci", "waterfall"):
        s = spec["series"][0]
        err = None
        if "y_hi" in s:
            err = dict(type="data", symmetric=False,
                       array=[hi - y for hi, y in zip(s["y_hi"], s["y"])],
                       arrayminus=[y - lo for lo, y in zip(s["y_lo"], s["y"])])
        if spec.get("horizontal"):
            colors = ["#d93025" if h else "#1a73e8" for h in s.get("highlight", [False] * len(s["x"]))]
            fig.add_trace(go.Bar(y=s["y"], x=s["x"], orientation="h", marker_color=colors))
        else:
            fig.add_trace(go.Bar(x=s["x"], y=s["y"], error_y=err, marker_color=s.get("color", "#1a73e8")))
    elif k == "line":
        s = spec["series"][0]
        fig.add_trace(go.Scatter(x=s["x"], y=s["y"], line=dict(color=s.get("color", "#d93025"), width=3)))
        for a in spec.get("annotations", []):
            if a.get("type") == "hline":
                fig.add_hline(y=a["y"], line_dash="dash", annotation_text=a.get("label", ""))
    elif k in ("tornado", "shap_bar"):
        s = spec["series"][0]
        pos, neg = "#d93025", "#1a73e8"
        if k == "shap_bar":
            pos, neg = "#1a73e8", "#d93025"
        fig.add_trace(go.Bar(y=s["y"], x=s["x"], orientation="h",
                             marker_color=[pos if v >= 0 else neg for v in s["x"]]))
    elif k == "scatter":
        pts = spec["series"][0]["points"]
        oth = [p for p in pts if not p["highlight"]]; hl = [p for p in pts if p["highlight"]]
        fig.add_trace(go.Scatter(x=[p["x"] for p in oth], y=[p["y"] for p in oth], mode="markers",
                                 marker=dict(size=10, color="#9aa0a6"), text=[p["coc"] for p in oth], name="cities"))
        if hl:
            fig.add_trace(go.Scatter(x=[p["x"] for p in hl], y=[p["y"] for p in hl], mode="markers+text",
                                     marker=dict(size=16, color="#d93025"), text=[p["coc"] for p in hl],
                                     textposition="top center", name="selected"))
    elif k == "dot_interval":
        for s in spec["series"]:
            err = None
            if "y_hi" in s:
                err = dict(type="data", symmetric=False, array=[s["y_hi"][0] - s["y"][0]],
                           arrayminus=[s["y"][0] - s["y_lo"][0]])
            fig.add_trace(go.Scatter(x=s["x"], y=s["y"], error_y=err, mode="markers",
                                     marker=dict(size=15, color=s.get("color")), name=s["name"]))
    elif k == "area":
        for s in spec["series"]:
            fig.add_trace(go.Scatter(x=s["x"], y=s["y"], stackgroup="one", name=s["name"], line=dict(color=s.get("color"))))
    elif k == "map":
        pts = spec["series"][0]["points"]
        fig.add_trace(go.Scattergeo(lon=[p["lon"] for p in pts], lat=[p["lat"] for p in pts],
                                    text=[f"{p['coc']}: {p['rate']}/1k" for p in pts],
                                    marker=dict(size=[max(6, p["rate"] * 2.2) for p in pts],
                                                color=["#d93025" if p["highlight"] else "#1a73e8" for p in pts])))
        fig.update_geos(scope="usa")
    fig.update_layout(title=spec.get("title"), height=420, margin=dict(l=10, r=10, t=44, b=10),
                      xaxis_title=spec.get("x_label"), yaxis_title=spec.get("y_label"),
                      legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)
    if spec.get("caption"):
        st.caption(spec["caption"])


@st.cache_data(show_spinner=False)
def get_cocs():
    return available_cocs()


@st.cache_data(show_spinner=False)
def get_params(coc):
    return build_params_for_coc(coc)


@st.cache_data(show_spinner=False)
def run_scenarios(coc, budget, delay, n_mc, mix_items):
    p = get_params(coc); mix = dict(mix_items)
    now = skills.run_simulation(p, skills.make_scenario(p, "Act now", delay=0, budget=budget, mix=mix), n_mc)
    dly = skills.run_simulation(p, skills.make_scenario(p, f"Delay {delay}y", delay=delay, budget=budget, mix=mix), n_mc)
    sq = skills.run_simulation(p, skills.make_scenario(p, "Status quo", budget=0.0), n_mc)
    return now, dly, sq


@st.cache_data(show_spinner=False)
def cached_effect_band(coc, budget, delay):
    return metrics.cost_of_waiting_effect_band(get_params(coc), {"budget_musd": budget, "delay_years": delay})


@st.cache_data(show_spinner=False)
def cached_backtest(coc):
    return skills.run_backtest(get_params(coc)) if coc == "CA-600" else None


with st.sidebar:
    st.header("City")
    cocs = get_cocs()
    labels = {f"{c['name']} ({c['coc']})": c["coc"] for c in cocs}
    pick = st.selectbox("Continuum of Care", list(labels.keys()), index=0)
    coc = labels[pick]
    if coc != "CA-600":
        st.caption("Illustrative: real PIT + model inflow; flow/cost are CA-600 priors.")
    st.divider()
    st.header("Scenario controls")
    budget = st.slider("Annual budget ($M)", 0.0, 200.0, 50.0, 5.0)
    delay = st.slider("Delay before acting (years)", 0, 10, 3, 1)
    n_mc = st.select_slider("Monte Carlo runs", [100, 200, 400, 800], value=200)
    st.markdown("**Intervention mix**")
    prev = st.slider("Prevention", 0.0, 1.0, 0.34, 0.01)
    rrh = st.slider("Rapid re-housing", 0.0, 1.0, 0.33, 0.01)
    psh = st.slider("Permanent supportive housing", 0.0, 1.0, 0.33, 0.01)
    tot = max(prev + rrh + psh, 1e-9)
    mix = {"prevention": prev / tot, "rapid_rehousing": rrh / tot, "permanent_supportive_housing": psh / tot}
    st.divider()
    use_gemma = st.toggle("Use offline Gemma planner", value=False,
                          help="Gemma 3n via Ollama. Falls back to rule-based if unavailable.")
    os.environ["WAITCOST_PLANNER"] = "gemma" if use_gemma else "rule"

params = get_params(coc)
st.title("WaitCost — The Cost of Doing Nothing")
st.caption(f"{params['meta']['coc']} · vintage: {params['meta']['data_vintage']}")
st.caption("Informs a budget-timing tradeoff. Does NOT decide allocations or forecast "
           "individuals. All figures are ranges, not predictions.")

tab_ask, tab_explore, tab_viz, tab_ai, tab_gov = st.tabs(
    ["💬 Ask the agent", "📈 Explore", "📊 Visualize", "🤖 Where's the AI", "🛡️ Governance & data"])

# ----------------------------------------------------------------------- Ask
with tab_ask:
    st.subheader("Ask a question — the agent figures out what kind it is")
    st.caption("Try: *What if we wait 3 years on a $15M program?* · *How long can we afford to "
               "wait?* · *How much do we save by acting now?* · *Is $15M or $50M better?* · "
               "*Should we fund prevention or supportive housing?* · *Which assumption are we "
               "least sure about?*")
    q = st.text_input("Question", "What if we wait 3 years on a $15M program?")
    if st.button("Run the agent", type="primary"):
        with st.spinner("Agent classifying, simulating, explaining…"):
            override = params if coc != "CA-600" else None
            agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1, params=override)
            result = agent.answer(q, out_dir="outputs")
        if result.get("out_of_scope"):
            st.warning("**Out of scope — by design.** " + result["reason"])
        elif result.get("declined"):
            st.error(f"Agent declined (data sufficiency): {result['reason']}")
        else:
            st.success(f"Question type: **{result['intent']}** · planner {result['plan']['planner']} · "
                       f"delay {result['plan']['delay_years']}y · budget ${result['plan']['budget_musd']}M")
            if result.get("direct_answer"):
                st.markdown("### " + result["direct_answer"])
            with st.expander("Agent trajectory (skills called, with Action Tier)"):
                st.dataframe(pd.DataFrame(result["trajectory"]), hide_index=True, use_container_width=True)
            if result.get("recommended_chart"):
                st.markdown(f"**Chart for this question** — the viz agent picked `{result['recommended_chart']}`:")
                try:
                    render_spec(viz.build_chart(result["recommended_chart"], coc=coc,
                                                budget=result["plan"]["budget_musd"],
                                                delay=result["plan"]["delay_years"], n_mc=150))
                except Exception as e:
                    st.info(f"Chart not available for this city: {e}")
            gloss = planner.explain_brief(result["brief_markdown"])
            if gloss:
                st.info("🗣️ Gemma summary: " + gloss)
            with st.expander("Full decision brief"):
                st.markdown(result["brief_markdown"])

    st.divider()
    st.markdown("**Tier-2 gate (human-in-the-loop).** Recommending a binding allocation is "
                "Action Tier 2 — the agent must stop and ask a human.")
    approve = st.checkbox("I approve the agent recommending a specific allocation (Tier 2)")
    if st.button("Recommend an allocation (Tier 2)"):
        agent = WaitCostAgent(PARAMS_PATH, max_auto_tier=1)
        try:
            agent._check_tier("optimize_allocation", approve=approve)
            st.success("✅ Human approved — Tier-2 step authorized and logged to MEMORY.md.")
        except TierViolation as e:
            st.warning(f"⛔ Blocked: {e} Tick the approval box to authorize.")

# ------------------------------------------------------------------- Explore
with tab_explore:
    now, dly, sq = run_scenarios(coc, budget, delay, n_mc, tuple(sorted(mix.items())))
    fig = go.Figure()
    for r, color in [(sq, "#9aa0a6"), (now, "#1a73e8"), (dly, "#d93025")]:
        b = r["bands"]; yrs = b["month"] / 12
        fig.add_trace(go.Scatter(x=yrs, y=b["p90"] / 1e6, line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=yrs, y=b["p10"] / 1e6, fill="tonexty", line=dict(width=0),
                                 opacity=0.15, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=yrs, y=b["p50"] / 1e6, line=dict(color=color, width=3), name=r["scenario"]))
    fig.update_layout(xaxis_title="Year", yaxis_title="Cumulative public cost ($M)",
                      height=440, legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

    cow = metrics.cost_of_waiting(now["mc_final"], dly["mc_final"])
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Cost of waiting {delay}y (P50)", usd(cow["extra_cost_median"]),
              help=f"80% range {usd(cow['extra_cost_p10'])} – {usd(cow['extra_cost_p90'])}")
    c2.metric("Act-now 10y cost (P50)", usd(now["final_cum_cost_p50"]))
    c3.metric("Active homeless at horizon (act now)", f"{now['final_active_homeless']:,.0f}")

    with st.expander("Assumption sensitivity — headline under ±50% intervention effect"):
        eb = cached_effect_band(coc, budget, delay)
        st.write(f"Cost-of-waiting ranges **{usd(eb['cow_at_lo'])} – {usd(eb['cow_at_hi'])}** "
                 f"across ±50% effect sizes. The *sign* (waiting costs more) is robust; the "
                 f"*magnitude* is a planning estimate.")

# ------------------------------------------------------------------- Visualize
with tab_viz:
    st.subheader("Visualization agent — the right chart for the question")
    st.caption("A specialist agent: it picks the decision chart and renders a spec built from "
               "real engine output. The same specs feed the React frontend via /chart.")
    catalog = viz.CHART_CATALOG
    label = {c["name"]: c["name"].replace("_", " ") for c in catalog}
    sel = st.selectbox("Chart", [c["name"] for c in catalog], format_func=lambda n: label[n])
    st.caption(next(c["when"] for c in catalog if c["name"] == sel))
    with st.spinner("Building chart from real data…"):
        render_spec(viz.build_chart(sel, coc=coc, budget=budget, delay=delay, n_mc=n_mc))

# --------------------------------------------------------------- Where's the AI
with tab_ai:
    im = skills.load_inflow_model()
    if not im:
        st.warning("Run `python scripts/train_inflow.py` to generate model/inflow_model.json.")
    else:
        st.caption(f"One model, trained on {len(get_cocs())} cities — it scores every city from "
                   f"that city's Census data.")
        st.caption("Refit on the API-sourced ACS panel (`scripts/fetch_acs.py`, verified 0/119 ≥5%); "
                   "held-out R² (≈0.36) and backtest (≈4%) unchanged by the refresh.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Model", im["model"])
        c2.metric("Held-out R² (LOO)", f"{im['loo_r2']:.2f}", help=f"in-sample {im['insample_r2']:.2f}")
        xv = im.get("spm_crossval") or {}
        if xv:
            c3.metric("ML vs HUD SPM (CA-600)", f"~{xv['agreement_pct_diff']:.0f}% apart",
                      help=f"ML {xv['ml_inflow_monthly']:.0f}/mo vs SPM M5 {xv['spm_inflow_monthly']:.0f}/mo")

        st.markdown("**SHAP — drivers of predicted homelessness (CA-600). Housing cost leads.**")
        sh = pd.DataFrame(im["shap_target"])
        fig2 = go.Figure(go.Bar(x=sh["shap"], y=sh["feature"], orientation="h",
                                marker_color=["#1a73e8" if v >= 0 else "#d93025" for v in sh["shap"]]))
        fig2.update_layout(height=260, xaxis_title="SHAP contribution (per 1,000)", margin=dict(l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)

        colA, colB = st.columns(2)
        with colA:
            df = pd.read_csv("data/coc_panel.csv")
            st.markdown(f"**Training data: {len(df)} cities ({pick} highlighted)**")
            df["rate"] = df["pit_total"] / df["population"] * 1000
            df["sel"] = df["coc"] == coc
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=df[~df.sel]["median_home_value"], y=df[~df.sel]["rate"],
                                      mode="markers", marker=dict(size=10, color="#9aa0a6"),
                                      text=df[~df.sel]["coc"], name="other cities"))
            fig3.add_trace(go.Scatter(x=df[df.sel]["median_home_value"], y=df[df.sel]["rate"],
                                      mode="markers+text", marker=dict(size=16, color="#d93025"),
                                      text=[coc], textposition="top center", name=coc))
            fig3.update_layout(height=320, xaxis_title="Median home value ($)",
                               yaxis_title="Homeless per 1,000", showlegend=False, margin=dict(l=10, r=10))
            st.plotly_chart(fig3, use_container_width=True)
        with colB:
            bt = cached_backtest(coc)
            if bt is None:
                st.markdown("**Face validity (backtest)**")
                st.info("The historical backtest is calibrated for CA-600 (Los Angeles). "
                        "Select Los Angeles to see the model reproduce the observed 2024 count.")
            else:
                st.markdown("**Face validity (backtest): seed 2023 → predict 2024**")
                fig4 = go.Figure()
                fig4.add_trace(go.Scatter(x=["2024 predicted"], y=[bt["predicted_active_p50"]],
                                          error_y=dict(type="data",
                                                       array=[bt["predicted_active_p90"] - bt["predicted_active_p50"]],
                                                       arrayminus=[bt["predicted_active_p50"] - bt["predicted_active_p10"]]),
                                          mode="markers", marker=dict(size=14, color="#1a73e8"), name="model"))
                fig4.add_trace(go.Scatter(x=["2024 predicted"], y=[bt["observed_2024_total"]],
                                          mode="markers", marker=dict(size=16, color="#188038", symbol="diamond"),
                                          name="observed"))
                fig4.update_layout(height=320, yaxis_title="Active homeless", margin=dict(l=10, r=10),
                                   legend=dict(orientation="h"))
                st.plotly_chart(fig4, use_container_width=True)
                verdict = "within" if bt["within_band"] else "outside"
                st.caption(f"Observed {bt['observed_2024_total']:,} is **{verdict}** the band "
                           f"({bt['abs_pct_error_p50']:.0f}% central error).")

# ------------------------------------------------------------------ Governance
with tab_gov:
    st.markdown(f"**City:** {params['meta']['coc']}  \n**Vintage:** {params['meta']['data_vintage']}")
    st.markdown("**Action Tiers** — Tier 0–1 automatic; Tier 2+ requires human approval.")
    st.table(pd.DataFrame([
        {"Tier": 0, "Examples": "load data, sensitivity, check data support", "Autonomy": "automatic"},
        {"Tier": 1, "Examples": "run simulation, backtest, write brief", "Autonomy": "automatic"},
        {"Tier": 2, "Examples": "recommend / finalize an allocation", "Autonomy": "human approval required"},
    ]))

    st.markdown("**Enforced bypass** — the agent declines rather than show unsupported bands.")
    demo = st.selectbox("Try a data condition", ["Real (sufficient)", "Sub-CoC geography",
                                                 "Thin homeless count", "Synthetic vintage"])
    p = copy.deepcopy(params)
    if demo == "Sub-CoC geography":
        p["meta"]["sub_coc"] = True
    elif demo == "Thin homeless count":
        for s in ACTIVE_HOMELESS:
            p["initial_population"][s] = 10
    elif demo == "Synthetic vintage":
        p["meta"]["data_vintage"] = "SYNTHETIC placeholder"
    try:
        skills.check_data_support(p)
        st.success("✅ Data is sufficient — the agent proceeds.")
    except skills.DataSufficiencyError as e:
        st.error(f"⛔ Declined: {e}")

    st.caption("The ACS economic features are reproducible from the Census API via "
               "`scripts/fetch_acs.py` and were verified against the original transcription "
               "(0 of 119 values differed ≥5%). See `data_sources/METHODOLOGY.md`.")
    with st.expander("Data sources (provenance)"):
        try:
            st.markdown(open("data/SOURCES.md").read())
        except OSError:
            st.write("See data/SOURCES.md")
