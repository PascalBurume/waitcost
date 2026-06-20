"""The capability registry — ONE declarative source of truth per intent.

Before this, a single intent's knowledge was duplicated across five structures
in ~seven files: planner.INTENTS, planner.classify_intent (regex), the
hand-written planner._PLAN_SYS Claude prompt, orchestrator._direct_answer (the
if/elif chain), tools.CAPABILITIES, and viz.INTENT_CHART. Adding one analysis
meant editing all of them and keeping them in sync by hand.

Now each capability is declared once (see `specs.py`) and the old structures are
*derived* from the registry, so they can never drift. This mirrors the Anthropic
Agent Skills idea: a capability carries its own name + description + "when to
use", and the rest is generated.

A capability is keyed by its `intent`. The REGISTRY is an ORDERED list whose
order IS the classification priority (e.g. `cost_per_person` is matched before
`out_of_scope` so an AGGREGATE "cost per person" isn't read as individual
profiling). Encoding that order in one place removes a hidden coupling.

`tier` here is the user-facing CATALOG tier (what `/tools` shows). The internal
Action-Tier guard the orchestrator enforces is keyed by low-level *skill* name
(orchestrator.ACTION_TIERS) — a deliberately separate concern, left as is.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple


@dataclass(frozen=True)
class Capability:
    intent: str                                   # canonical id (the planner intent)
    summary: str                                  # short menu line  -> progressive-disclosure list
    when_to_use: str                              # routing hint     -> _PLAN_SYS meaning + skill desc
    params: Tuple[str, ...] = ()                  # planner-filled   -> CAPABILITIES params
    triggers: Tuple = ()                          # ordered matchers -> classify_intent (regex or q->bool)
    handler: Optional[Callable] = None            # dispatch target  -> replaces a _direct_answer branch
    chart: Optional[str] = None                   # chart name       -> INTENT_CHART
    runs_engine: bool = True                      # False = greeting/clarify/out_of_scope (skip pipeline)
    plan_example: Optional[str] = None            # one Q->JSON few-shot -> _PLAN_SYS
    # Catalog metadata: only the rows that appear in the user-facing tools.CAPABILITIES.
    in_catalog: bool = False
    catalog_tier: int = 0
    catalog_order: int = 0
    catalog_desc: str = ""


# Infra capabilities that are NOT intents but DO appear in the public catalog
# (the planner never routes to these; they are engine "hands" / the viz + Tier-2
# rows). Kept as a small static side-table so the derived catalog reproduces the
# exact historical tools.CAPABILITIES list (name/tier/params/desc + order).
@dataclass(frozen=True)
class InfraCapability:
    name: str
    tier: int
    params: Tuple[str, ...]
    desc: str
    catalog_order: int


INFRA_CAPS: Tuple[InfraCapability, ...] = (
    InfraCapability(
        "retrieve_us_context", 0, ("coc",),
        "Retrieve essential US public indicators for a city (population, homelessness, "
        "housing cost, income, poverty, rent burden) to inform the decision.", 0),
    InfraCapability(
        "visualize", 0, ("chart", "coc"),
        "Pick and render the right decision chart for a question (the viz agent).", 14),
    InfraCapability(
        "recommend_allocation", 2, ("budget_musd",),
        "Recommend a specific binding allocation — Tier 2, requires human approval.", 15),
)


REGISTRY: list = []                 # populated by specs.register() at import time
_BY_INTENT: dict = {}


def register(cap: Capability) -> Capability:
    """Append a capability (call order == classification priority)."""
    if cap.intent in _BY_INTENT:
        raise ValueError(f"duplicate capability intent: {cap.intent}")
    REGISTRY.append(cap)
    _BY_INTENT[cap.intent] = cap
    return cap


def by_intent(intent: str) -> Optional[Capability]:
    return _BY_INTENT.get(intent)


# --- derived views (the old structures, generated so they can't drift) ------
def intents_tuple() -> Tuple[str, ...]:
    """Replaces planner.INTENTS. Membership is what callers use; order is cosmetic."""
    return tuple(c.intent for c in REGISTRY)


def classify(q: str) -> str:
    """Replaces the body of planner.classify_intent: walk the registry in priority
    order, return the first intent whose triggers match. A trigger is either a
    compiled regex (`.search`) or a predicate `q -> bool`."""
    ql = (q or "").lower()
    for cap in REGISTRY:
        for t in cap.triggers:
            hit = t.search(ql) if hasattr(t, "search") else t(ql)
            if hit:
                return cap.intent
    return None   # caller applies the in-scope-vs-clarify fallback


def intent_chart_map() -> dict:
    """The intent->chart bindings owned by the registry (merged with viz's own
    non-intent entries like `model`/`explore` on the viz side)."""
    return {c.intent: c.chart for c in REGISTRY if c.chart}


def capabilities_catalog() -> list:
    """Replaces the literal tools.CAPABILITIES — infra rows + in-catalog intents,
    emitted in the historical display order."""
    rows = [{"name": ic.name, "tier": ic.tier, "params": list(ic.params),
             "desc": ic.desc, "_order": ic.catalog_order} for ic in INFRA_CAPS]
    rows += [{"name": c.intent, "tier": c.catalog_tier, "params": list(c.params),
              "desc": c.catalog_desc, "_order": c.catalog_order}
             for c in REGISTRY if c.in_catalog]
    rows.sort(key=lambda r: r["_order"])
    return [{k: v for k, v in r.items() if k != "_order"} for r in rows]


# JSON-schema fragments for the params a capability can accept. The Phase-2 tool
# loop derives each tool's input_schema from `cap.params`, so the Anthropic tool
# set is generated from the SAME registry as routing and the planner prompt — a
# third consumer that can never drift from the intents.
_PARAM_SCHEMA = {
    "budget_musd": {"type": "number",
                    "description": "Annual program budget in millions of USD."},
    "delay_years": {"type": "integer",
                    "description": "Years to wait before acting (0 = act now)."},
    "budgets": {"type": "array", "items": {"type": "number"},
                "description": "Two or more annual budgets in $M to compare."},
    "coc": {"type": "string",
            "description": "Continuum-of-Care code, e.g. CA-600."},
}


def anthropic_tools() -> list:
    """Anthropic tool schemas for the engine-running, handler-backed capabilities
    (the Phase-2 tool-use loop). `name` is the intent, `description` is its
    `when_to_use`, and the input schema is derived from `cap.params`. Required is
    left empty: the orchestrator fills any missing arg from the canonical plan, so
    a tool call with partial args still runs."""
    tools = []
    for c in REGISTRY:
        if not (c.runs_engine and c.handler):
            continue   # skip greeting/clarify/out_of_scope and retrieval-only intents
        props = {p: _PARAM_SCHEMA[p] for p in c.params if p in _PARAM_SCHEMA}
        tools.append({
            "name": c.intent,
            "description": c.when_to_use,
            "input_schema": {"type": "object", "properties": props, "required": []},
        })
    return tools


def plan_meanings() -> str:
    """`intent=meaning` lines for the generated planner system prompt."""
    return "\n".join(f"{c.intent}={c.when_to_use}" for c in REGISTRY)


def plan_examples(default) -> str:
    """The few-shot Q->JSON examples for the generated Claude system prompt."""
    return "\n".join(c.plan_example % {"default": default}
                     for c in REGISTRY if c.plan_example)
