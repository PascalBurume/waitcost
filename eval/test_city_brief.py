"""Tests for the third agent — CityBriefAgent (grounded, cited city briefings).

Auto-collected (test_*.py). conftest pins WAITCOST_PLANNER=rule so no Ollama is
needed and the deterministic, fully-grounded path is exercised.
"""
import json
import os

import pytest

from agent import planner
from agent.city_brief import CityBriefAgent, LABEL
from agent.orchestrator import WaitCostAgent

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS_PATH = os.path.join(REPO, "config", "params.yaml")
REGISTRY_PATH = os.path.join(REPO, "data", "city_sources.json")
SAMPLE_COCS = ["CA-600", "WA-500", "CA-601"]


@pytest.fixture(scope="module")
def registry():
    with open(REGISTRY_PATH) as f:
        return json.load(f)


# --- 1. Registry integrity --------------------------------------------------
def test_registry_has_17_complete_cocs(registry):
    cities = registry["cities"]
    assert len(cities) == 17
    for c in cities:
        assert c.get("lead_agency"), c.get("coc")
        assert c.get("plan_title"), c.get("coc")
        assert c.get("key_sources") and c["key_sources"][0].get("url"), c.get("coc")


def test_national_frameworks_present(registry):
    titles = " ".join(f.get("title", "") for f in registry["national_frameworks"])
    assert "All In" in titles and "Continuum of Care" in titles


# --- 2. Brief output contract ----------------------------------------------
@pytest.mark.parametrize("coc", SAMPLE_COCS)
def test_brief_contract(coc):
    b = CityBriefAgent().brief(coc)
    assert b["situation"].strip()
    assert b["plan"]["url"]
    assert b["sources"] and all(s["url"] for s in b["sources"])
    assert b["label"] == LABEL
    assert b["lead_agency"]
    assert "national_context" in b and b["national_context"]
    assert b["trajectory"]                     # records its Tier-0 steps


# --- 3. Number guard: every figure traces to the engine / registry ----------
@pytest.mark.parametrize("coc", SAMPLE_COCS)
def test_brief_numbers_are_grounded(coc):
    agent = CityBriefAgent()
    b = agent.brief(coc)
    note = next((c.get("situation_note", "") for c in agent._registry["cities"]
                 if c["coc"] == coc), "")
    allowed = agent._fact_whitelist(b["indicators"], note, None, b["plan"]["title"])
    # The equity headline (if woven in) is itself grounded engine output; include it.
    try:
        from analysis.equity import headline
        allowed += "\n" + (headline(coc) or "")
    except Exception:
        pass
    assert planner.numbers_are_grounded(b["situation"], allowed), b["situation"]
    assert planner.numbers_are_grounded(b["plan"]["summary"], allowed), b["plan"]["summary"]


def test_indicators_match_engine():
    from agent import skills
    b = CityBriefAgent().brief("CA-600")
    eng = skills.retrieve_us_context("CA-600")["indicators"]
    assert b["indicators"]["homeless_pit_total"] == eng["homeless_pit_total"] == 71201


# --- 4. Routing through the orchestrator front door -------------------------
def test_care_plan_routes_to_city_brief():
    agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1)
    res = agent.answer("What is the city's plan and strategy?", out_dir="outputs")
    assert res["intent"] == "care_plan"
    assert "city_brief" in res and res["city_brief"]["label"] == LABEL
    assert "runs" not in res                   # the cost engine never ran
    skills_run = [s["skill"] for s in res["trajectory"]]
    assert "route_city_brief" in skills_run    # the hand-off is visible
    assert "run_simulation" not in skills_run


def test_city_situation_routes_to_city_brief():
    agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1)
    res = agent.answer("Tell me about the homelessness situation here", out_dir="outputs")
    assert res["intent"] == "city_situation"
    assert "city_brief" in res
    assert "not the calibrated cost model" in res["label"]


# --- 5. Individual-level questions are declined, not briefed ----------------
def test_individual_question_declined_not_briefed():
    agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1)
    res = agent.answer("Which family will become homeless in Chicago?", out_dir="outputs")
    assert res.get("declined") and res.get("out_of_scope")
    assert "city_brief" not in res


# --- 6. Offline-first / opt-in live mode -----------------------------------
def test_offline_is_default(monkeypatch):
    monkeypatch.delenv("WAITCOST_ONLINE", raising=False)
    b = CityBriefAgent().brief("WA-500")
    assert b["online"] is False
    assert b["sources"]                        # still cited from the registry


def test_online_flag_augments_when_fetch_succeeds(monkeypatch):
    monkeypatch.setenv("WAITCOST_ONLINE", "1")
    from agent import web_search
    monkeypatch.setattr(web_search, "fetch", lambda url: "<html>live</html>")
    b = CityBriefAgent().brief("WA-500")
    assert b["online"] is True
    # the refreshed plan URL is cited (every live fact carries its URL in sources)
    assert any(s["url"] == b["plan"]["url"] for s in b["sources"])


def test_online_flag_degrades_when_fetch_fails(monkeypatch):
    monkeypatch.setenv("WAITCOST_ONLINE", "1")
    from agent import web_search
    monkeypatch.setattr(web_search, "fetch", lambda url: None)   # network down / moved link
    b = CityBriefAgent().brief("WA-500")
    assert b["online"] is False                # never breaks; falls back to offline
    assert b["sources"]


# --- 7. Number-guard fallback: invented figure -> deterministic template -----
def test_narration_with_invented_number_is_rejected(monkeypatch):
    # Force the generic narrator to emit a figure NOT in the facts; the guard must
    # reject it so the caller keeps the deterministic, grounded text.
    monkeypatch.setenv("WAITCOST_PLANNER", "gemma")
    monkeypatch.setattr(planner, "gemma_available", lambda: True)
    monkeypatch.setattr(planner, "_ollama_generate",
                        lambda *a, **k: "The city spent $999,123,456 on a brand-new program.")
    out = planner.narrate_grounded("prompt", "homeless_pit_total: 16868")
    assert out is None                         # invented number rejected
