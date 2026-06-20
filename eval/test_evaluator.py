"""The Evaluator agent (5th agent) + confidence-gated routing.

Unit tests on `evaluator.evaluate(...)` (pure, no network) plus two orchestrator-
level tests that mock the LLM for the confidence gate and the self-correction loop.
conftest pins WAITCOST_PLANNER=rule; tests that need the Claude path set it +
monkeypatch agent.llm.generate.
"""
import os

from agent import evaluator, llm, planner
from agent.orchestrator import WaitCostAgent

PARAMS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "config", "params.yaml")

LA = {"meta": {"coc": "CA-600 Los Angeles City & County CoC",
               "data_vintage": "HUD 2024 PIT + Census ACS 2024 (API)"}}
ILLUSTRATIVE = {"meta": {"coc": "WA-500 Seattle/King County",
                         "data_vintage": "HUD 2024 PIT (real) + ACS; flow rates & costs are "
                                         "CA-600 priors — local calibration pending"}}

_COW = {"cost_of_waiting": {"extra_cost_median": 345.6e6,
                            "extra_cost_p10": 282.4e6, "extra_cost_p90": 411.1e6}}


def _result(intent="cost_of_waiting",
            direct="**Waiting 3 years costs about $345.6M more** over 10 years "
                   "(80% range $282.4M – $411.1M).",
            brief_author="deterministic", brief_markdown="Deterministic memo.",
            plan=None, comparison=None):
    return {"intent": intent, "direct_answer": direct, "brief_markdown": brief_markdown,
            "brief_author": brief_author, "comparison": comparison or _COW,
            "plan": plan or {"intent": intent}}


# --- deterministic checks 1–5 (pure) ----------------------------------------
def test_valid_answer_passes():
    rc = evaluator.evaluate("What if we wait 3 years on a $15M program?",
                            _result(), LA, facts={"cost_of_waiting_median": "$345.6M"})
    assert rc["status"] == "pass"
    assert all(c["status"] == "ok" for c in rc["checks"])
    assert rc["what_went_wrong"] == []


def test_illustrative_city_warns_not_blocks():
    rc = evaluator.evaluate("cost of waiting 3 years at $15M?", _result(),
                            ILLUSTRATIVE, facts={"cost_of_waiting_median": "$345.6M"})
    assert rc["status"] == "warn"        # annotate-first: shown with a caveat, not blocked
    assert any(c["name"] == "data" and c["status"] == "warn" for c in rc["checks"])


def test_default_budget_warns():
    res = _result(plan={"intent": "cost_of_waiting", "defaults_used": ["a budget"]})
    rc = evaluator.evaluate("what does waiting 3 years cost?", res, LA)
    assert rc["status"] == "warn"
    assert any(c["name"] == "parameters" and c["status"] == "warn" for c in rc["checks"])


def test_scope_leak_declines():
    rc = evaluator.evaluate("Which family on 5th Street will become homeless next year?",
                            _result(), LA)
    assert rc["status"] == "decline"
    assert any(c["name"] == "scope" and c["status"] == "fail" for c in rc["checks"])
    assert rc["suggested_reformulation"]


def test_fabricated_number_in_claude_memo_repairs():
    # A raw LLM memo with a figure the engine never produced → grounding fail → repair.
    rc = evaluator.evaluate("cost of waiting?", _result(), LA,
                            facts={"cost_of_waiting_median": "$345.6M"},
                            llm_memo="## Decision memo\nWaiting will cost $999.9M — a fabricated figure.")
    assert rc["status"] == "repair"
    assert any(c["name"] == "grounding" and c["status"] == "fail" for c in rc["checks"])


def test_deterministic_brief_is_not_falsely_flagged():
    # No raw LLM memo (deterministic brief) → grounding is ok by construction; the
    # engine-grounded verdict-citation prefix is never re-grounded against the facts.
    rc = evaluator.evaluate("cost of waiting?", _result(), LA,
                            facts={"cost_of_waiting_median": "$345.6M"}, llm_memo=None)
    assert rc["status"] == "pass"
    assert any(c["name"] == "grounding" and c["status"] == "ok" for c in rc["checks"])


def test_chart_text_mismatch_repairs():
    res = _result(direct="**Waiting 3 years costs about $999M more** over 10 years.")
    rc = evaluator.evaluate("cost of waiting 3 years at $15M?", res, LA)
    assert rc["status"] == "repair"
    assert any(c["name"] == "chart_text" and c["status"] == "fail" for c in rc["checks"])


def test_question_match_judge_failure_repairs():
    rc = evaluator.evaluate("How long can we wait?", _result(), LA, facts={},
                            question_match={"ok": False, "reason": "answered cost, not break-even"})
    assert rc["status"] == "repair"
    assert any(c["name"] == "question_match" and c["status"] == "fail" for c in rc["checks"])


def test_no_engine_figure_invented():
    # The evaluator never introduces a number the engine didn't produce: its
    # what_went_wrong strings are prose, and on a clean answer there are none.
    rc = evaluator.evaluate("cost of waiting 3 years at $15M?", _result(), LA,
                            facts={"cost_of_waiting_median": "$345.6M"})
    assert rc["status"] == "pass" and rc["what_went_wrong"] == []


# --- confidence-gated routing (orchestrator-level, mocked LLM) ---------------
def test_confidence_gate_routes_to_clarify(monkeypatch):
    monkeypatch.setenv("WAITCOST_PLANNER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(planner.llm, "generate", lambda *a, **k:
        '{"intent":"care_plan","delay_years":5,"budget_musd":15,"budgets":null,'
        '"route_confidence":0.3,"second_choice":"roi"}')
    p = planner.plan("What is the ROI of the city plan?", {"meta": {"default_budget_musd": 10.0}})
    assert p["intent"] == "clarify"
    assert p.get("route_alternatives") and len(p["route_alternatives"]) >= 2


def test_high_confidence_does_not_gate(monkeypatch):
    monkeypatch.setenv("WAITCOST_PLANNER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(planner.llm, "generate", lambda *a, **k:
        '{"intent":"care_plan","delay_years":5,"budget_musd":15,"budgets":null,'
        '"route_confidence":0.95,"second_choice":null}')
    p = planner.plan("What is the ROI of the city plan?", {"meta": {"default_budget_musd": 10.0}})
    assert p["intent"] == "care_plan"      # committed; no clarify


def test_safety_rail_beats_confidence_gate(monkeypatch):
    monkeypatch.setenv("WAITCOST_PLANNER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(planner.llm, "generate", lambda *a, **k:
        '{"intent":"care_plan","delay_years":5,"budget_musd":15,"budgets":null,'
        '"route_confidence":0.2,"second_choice":"roi"}')
    p = planner.plan("What's the plan for the family at 12 Elm Street?",
                     {"meta": {"default_budget_musd": 10.0}})
    assert p["intent"] == "out_of_scope" and p.get("safety_override")


# --- self-correction loop (orchestrator-level, mocked judge) ----------------
def test_self_correction_recovers_then_passes(monkeypatch):
    monkeypatch.setenv("WAITCOST_PLANNER", "rule")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    calls = {"n": 0}

    def judge(*a, **k):
        calls["n"] += 1
        return '{"ok": false, "reason": "mismatch"}' if calls["n"] == 1 else '{"ok": true}'

    monkeypatch.setattr(llm, "generate", judge)
    r = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1).answer(
        "What if we wait 3 years on a $15M program?", out_dir="outputs")
    assert calls["n"] == 2                 # 1 initial + 1 retry
    assert r.get("repaired") and r["response_check"]["status"] != "decline"


def test_self_correction_caps_then_warns_not_declines(monkeypatch):
    # Judge always says "mismatch". After ONE retry it still fails ONLY question_match
    # (deterministic checks all pass) → must downgrade to a WARN (answer shown with a
    # caveat), never a wrongful refusal (F8). Decline is reserved for hard correctness
    # failures (grounding/scope/chart).
    monkeypatch.setenv("WAITCOST_PLANNER", "rule")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    calls = {"n": 0}

    def judge(*a, **k):
        calls["n"] += 1
        return '{"ok": false, "reason": "still mismatch"}'

    monkeypatch.setattr(llm, "generate", judge)
    r = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1).answer(
        "What if we wait 3 years on a $15M program?", out_dir="outputs")
    assert calls["n"] == 2                 # capped: 1 initial + 1 retry, no more
    assert not r.get("declined")           # NOT a wrongful refusal
    assert r["response_check"]["status"] == "warn"
    assert r.get("direct_answer")          # the real answer is still shown
