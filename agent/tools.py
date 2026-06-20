"""Tool registry — the agent's function-calling catalog.

This is the explicit list of capabilities the agent can invoke. The small
offline planner (Claude) only has to pick the right `name` and fill simple
`params`; the deterministic Python behind each tool does the real computation
(the "sandbox"), and the result is narrated back in English. Nothing here does
maths in the language model.

Each entry: name · plain description · Action Tier · the simple params the
planner fills · the engine function that actually runs.
"""
from agent import capabilities as _caps

# tier: 0 read-only · 1 reversible compute · 2 needs human approval
# DERIVED from the capability registry (agent/capabilities) so the public catalog
# can never drift from the routing / prompt / chart bindings. The registry holds
# the answerable intents; the infra rows (retrieve_us_context, visualize,
# recommend_allocation) come from its INFRA_CAPS side-table.
CAPABILITIES = _caps.capabilities_catalog()


def list_capabilities():
    """The catalog (without the bound function) — safe to serialize / display."""
    return [{k: v for k, v in c.items()} for c in CAPABILITIES]


def capability_names():
    return [c["name"] for c in CAPABILITIES]


def tier_of(name):
    for c in CAPABILITIES:
        if c["name"] == name:
            return c["tier"]
    return 0


# Low-level skills the capabilities are built from (the engine "hands").
SKILLS = [
    "fetch_hud_data", "check_data_support", "retrieve_us_context", "load_inflow_model",
    "make_scenario", "run_simulation", "compare_scenarios", "sensitivity_report",
    "run_backtest", "effect_sensitivity", "compare_budgets", "compare_mix",
    "regional_cost_of_waiting", "write_brief", "load_city_sources", "synthesize_decision",
]


def registry_summary():
    """Five agents: the analyst (plans + runs tools), the viz specialist (charts),
    the city-brief agent (grounded, cited context), the decision agent (turns the
    scenario numbers into a plain-English recommendation), and the evaluator — the
    post-answer critic that checks every answer before the user sees it."""
    from analysis.viz import CHART_CATALOG
    return {"agents": 5,
            "agent_names": ["analyst", "visualization", "city_brief", "decision", "evaluator"],
            "capabilities": len(CAPABILITIES), "skills": len(SKILLS),
            "charts": len(CHART_CATALOG),
            "capability_names": capability_names(), "skill_names": SKILLS,
            "chart_names": [c["name"] for c in CHART_CATALOG]}
