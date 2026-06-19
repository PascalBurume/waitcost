"""State definitions and the Scenario object."""
from dataclasses import dataclass, field
from typing import Dict

# Order matters: vectors below are indexed in this order.
STATES = [
    "housed_stable",
    "at_risk",
    "sheltered",
    "unsheltered",
    "chronic_unsheltered",
    "exited_positive",
]

# States that count as "currently experiencing homelessness".
ACTIVE_HOMELESS = ["sheltered", "unsheltered", "chronic_unsheltered"]

_DEFAULT_MIX = {
    "prevention": 0.34,
    "rapid_rehousing": 0.33,
    "permanent_supportive_housing": 0.33,
}


@dataclass
class Scenario:
    """A policy scenario: how much to spend, when to start, and on what mix."""
    name: str
    annual_budget_musd: float = 0.0          # total annual intervention budget ($ millions)
    start_year: int = 0                       # year intervention begins (0 = now)
    mix: Dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_MIX))

    def active(self, month: int) -> bool:
        return month >= self.start_year * 12
