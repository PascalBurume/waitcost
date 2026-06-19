"""Step-2 safety net: the registry's derived views must EXACTLY reproduce the
historical literals before any caller is repointed at them. If these pass, the
later migration steps (repointing planner / orchestrator / viz / tools) are pure
refactors that cannot change behaviour.
"""
import re

from agent import capabilities as caps


# The literals as they stood before the refactor (transcribed once, here, as the
# golden reference).
LEGACY_INTENTS = (
    "cost_of_waiting", "break_even", "savings_now", "outcome_at_horizon",
    "compare_budgets", "compare_mix", "sensitivity", "roi", "cost_per_person",
    "regional", "uncertainty", "city_context", "equity",
    "greeting", "clarify", "out_of_scope",
    # CityBriefAgent (third agent) intents — qualitative/contextual, no engine.
    "care_plan", "city_situation",
    # Retrieval tools (kind=retrieval) — cited offline answers, no engine.
    "data_lookup", "concept_qa")

LEGACY_INTENT_CHART = {
    "cost_of_waiting": "cost_of_waiting", "break_even": "break_even_curve",
    "savings_now": "scenario_costs", "outcome_at_horizon": "people_helped",
    "compare_budgets": "budget_comparison", "compare_mix": "mix_comparison",
    "sensitivity": "sensitivity_tornado", "roi": "roi", "cost_per_person": "people_helped",
    "regional": "regional_waiting", "uncertainty": "sensitivity_tornado",
    "city_context": "city_benchmark", "equity": "equity_disparity",
    "care_plan": "city_benchmark", "city_situation": "city_benchmark"}

LEGACY_CAPABILITIES = [
    {"name": "retrieve_us_context", "tier": 0, "params": ["coc"],
     "desc": "Retrieve essential US public indicators for a city (population, homelessness, "
             "housing cost, income, poverty, rent burden) to inform the decision."},
    {"name": "cost_of_waiting", "tier": 1, "params": ["delay_years", "budget_musd"],
     "desc": "Extra 10-year public cost of waiting N years before acting, with a range."},
    {"name": "break_even", "tier": 1, "params": ["budget_musd"],
     "desc": "How long the city can wait before delaying stops paying off."},
    {"name": "savings_now", "tier": 1, "params": ["budget_musd"],
     "desc": "How much acting now saves (or costs) vs doing nothing."},
    {"name": "outcome_at_horizon", "tier": 1, "params": [],
     "desc": "Projected number of people homeless at the 10-year horizon."},
    {"name": "compare_budgets", "tier": 1, "params": ["budgets"],
     "desc": "Compare two or more annual budgets by 10-year cost and savings."},
    {"name": "compare_mix", "tier": 1, "params": ["budget_musd"],
     "desc": "Compare prevention / rapid-rehousing / supportive-housing spending mixes."},
    {"name": "sensitivity", "tier": 0, "params": [],
     "desc": "Which assumption the result is most sensitive to (what to tighten first)."},
    {"name": "roi", "tier": 1, "params": ["budget_musd"],
     "desc": "Return on investment / benefit-cost ratio of acting now (avoided cost per $ spent)."},
    {"name": "cost_per_person", "tier": 1, "params": ["budget_musd"],
     "desc": "People kept out of homelessness by acting now, and avoided public cost per person."},
    {"name": "regional", "tier": 1, "params": ["budget_musd", "delay_years"],
     "desc": "Rank the cost of waiting across multiple cities (same engine, real per-city data)."},
    {"name": "uncertainty", "tier": 0, "params": [],
     "desc": "How confident the headline is: the range, the weakest assumption, the backtest error."},
    {"name": "city_context", "tier": 0, "params": ["coc"],
     "desc": "Plain-language numeric profile of a city's homelessness + housing indicators."},
    {"name": "equity", "tier": 0, "params": ["coc"],
     "desc": "Population-level racial/demographic disparities (who bears homelessness, who is "
             "most unsheltered) — never profiles individuals."},
    {"name": "visualize", "tier": 0, "params": ["chart", "coc"],
     "desc": "Pick and render the right decision chart for a question (the viz agent)."},
    {"name": "recommend_allocation", "tier": 2, "params": ["budget_musd"],
     "desc": "Recommend a specific binding allocation — Tier 2, requires human approval."},
]


def test_intents_membership_matches_legacy():
    assert set(caps.intents_tuple()) == set(LEGACY_INTENTS)


def test_intent_chart_map_matches_legacy():
    assert caps.intent_chart_map() == LEGACY_INTENT_CHART


def test_capabilities_catalog_matches_legacy():
    assert caps.capabilities_catalog() == LEGACY_CAPABILITIES


def test_classify_reproduces_legacy_routing():
    # A spot-check of the ordering-sensitive cases the regex priority guards.
    cases = {
        "Hi, what can you do?": "greeting",
        "How many people would acting now help?": "cost_per_person",
        "Which family by name will become homeless?": "out_of_scope",
        "What's the racial disparity in homelessness?": "equity",
        "Which cities pay the most for waiting?": "regional",
        # narrative phrasings now route to the CityBriefAgent (city_situation/care_plan)
        "Tell me about Los Angeles": "city_situation",
        "What is the city's plan?": "care_plan",
        "Show me the housing cost-of-living profile": "city_context",
        "How long can we wait before it stops paying off?": "break_even",
        "Should we fund prevention or supportive housing?": "compare_mix",
        "Is $15M or $50M better?": "compare_budgets",
        "What is the ROI on a $15M program?": "roi",
        "How much do we save by acting now?": "savings_now",
        "How many people will be homeless in 2030?": "outcome_at_horizon",
        "How confident are you in that number?": "uncertainty",
        "Which assumption matters most?": "sensitivity",
    }
    for q, expected in cases.items():
        assert caps.classify(q) == expected, (q, caps.classify(q))


def test_every_engine_intent_has_handler():
    for c in caps.REGISTRY:
        if c.runs_engine:
            assert c.handler is not None, c.intent
        else:
            assert c.handler is None, c.intent


def test_classify_is_registry_ordered():
    # cost_per_person must precede out_of_scope (aggregate, not individual).
    intents = [c.intent for c in caps.REGISTRY]
    assert intents.index("cost_per_person") < intents.index("out_of_scope")
    assert intents.index("roi") < intents.index("savings_now")
    assert intents.index("uncertainty") < intents.index("sensitivity")
