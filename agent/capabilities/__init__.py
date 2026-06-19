"""Capability registry package — import this to get the populated REGISTRY.

`registry` defines the machinery; `specs` declares the capabilities (its import
side-effect runs every `register(...)`). Import order matters: machinery first,
declarations second.
"""
from agent.capabilities import registry as _registry
from agent.capabilities import specs as _specs   # noqa: F401  (registers capabilities)

from agent.capabilities.registry import (  # noqa: F401
    Capability,
    INFRA_CAPS,
    REGISTRY,
    by_intent,
    capabilities_catalog,
    classify,
    intent_chart_map,
    intents_tuple,
    plan_examples,
    plan_meanings,
    register,
)
