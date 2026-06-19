"""Tests for the fourth agent — DecisionAgent (plain-English recommendation).

Most tests are pure-unit (synthetic scenario dicts, no engine) so they're fast and
deterministic; one integration test runs the real orchestrator path.
"""
import os

from agent.decision import DecisionAgent
from agent.orchestrator import WaitCostAgent

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS_PATH = os.path.join(REPO, "config", "params.yaml")


def _ctx(cow_med, p10, p90, band, save=30e6, be_year=4, baseline=5_000e6, delay=5):
    runs = {"status_quo": {"final_cum_cost_p50": baseline}}
    comparison = {
        "cost_of_waiting": {"extra_cost_median": cow_med, "extra_cost_p10": p10, "extra_cost_p90": p90},
        "savings_vs_status_quo": {"savings_median": save},
        "break_even": {"break_even_year": be_year},
        "delay_years": delay,
    }
    effect_band = {"cow_at_lo": band[0], "cow_base": band[1], "cow_at_hi": band[2]}
    return runs, comparison, effect_band


def test_strong_signal_is_act_now_high_confidence():
    runs, comp, band = _ctx(100e6, 50e6, 150e6, band=(40e6, 100e6, 160e6))
    d = DecisionAgent().recommend({}, {"delay_years": 5}, runs, comp, effect_band=band)
    assert d["verdict"] == "act_now"
    assert d["direction_confidence"] == "high"
    assert d["verdict_label"] == "Act now"


def test_band_crossing_zero_lowers_confidence():
    # cost-of-waiting positive, but under +/-50% effects the sign flips -> not robust.
    runs, comp, band = _ctx(45e6, 11e6, 94e6, band=(-45e6, 45e6, 130e6))
    d = DecisionAgent().recommend({}, {"delay_years": 5}, runs, comp, effect_band=band)
    assert d["verdict"] == "lean_act_now"
    assert d["direction_confidence"] == "low"


def test_summary_explains_baseline_vs_slice():
    runs, comp, band = _ctx(100e6, 50e6, 150e6, band=(40e6, 100e6, 160e6))
    d = DecisionAgent().recommend({}, {"delay_years": 5}, runs, comp, effect_band=band)
    s = d["plain_summary"].lower()
    assert "no matter what" in s            # the baseline-is-locked-in framing
    assert "slice" in s                     # the decision moves a smaller slice
    assert "deadline" in s or "year" in s   # the break-even deadline


def test_evidence_numbers_match_inputs():
    runs, comp, band = _ctx(100e6, 50e6, 150e6, band=(40e6, 100e6, 160e6), save=30e6, be_year=4, baseline=5_000e6)
    d = DecisionAgent().recommend({}, {"delay_years": 5}, runs, comp, effect_band=band)
    e = d["evidence"]
    assert e["cost_of_waiting_musd"] == 100.0
    assert e["cost_of_waiting_range_musd"] == [50.0, 150.0]
    assert e["savings_now_musd"] == 30.0
    assert e["break_even_year"] == 4
    assert e["baseline_10yr_musd"] == 5000.0


def test_plain_summary_invents_no_number():
    """Every figure in the (deterministic) summary traces to the evidence — the
    same number-guard standard the rest of the system holds to."""
    from agent import planner
    runs, comp, band = _ctx(100e6, 50e6, 150e6, band=(40e6, 100e6, 160e6))
    d = DecisionAgent().recommend({}, {"delay_years": 5}, runs, comp, effect_band=band)
    allowed = " ".join([
        "$100.0M", "$50.0M", "$150.0M", "$30.0M", "$5,000.0M", "$5.0B", "year 4", "5 years",
    ])
    assert planner.numbers_are_grounded(d["plain_summary"], allowed), d["plain_summary"]


# --- integration: the decision rides along in /ask and the brief ---------------
def test_decision_present_in_agent_result_and_brief():
    agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1)
    res = agent.answer("What does it cost to wait 3 years on a $15M program?", out_dir="outputs")
    d = res.get("decision")
    assert d and d["verdict"] in ("act_now", "lean_act_now", "can_wait", "review")
    assert d["plain_summary"]
    # the brief leads with the plain-English recommendation + demystifies Monte Carlo
    md = res["brief_markdown"]
    assert "recommendation" in md.lower()
    assert "monte carlo" in md.lower() and "three futures" in md.lower()
    # the three Monte-Carlo runs are now distinguishable in the trajectory
    details = [s.get("detail", "") for s in res["trajectory"] if s["skill"] == "run_simulation"]
    assert any("do nothing" in x for x in details) and any("act now" in x for x in details)
    # the decision agent's own step is recorded
    assert any(s["skill"] == "synthesize_decision" for s in res["trajectory"])
