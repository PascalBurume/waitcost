"""Duration-aware cost accrual. Per-person cost rises with time-in-state."""
import numpy as np


def per_person_monthly(base_cost, tenure_years, duration_multiplier_per_year):
    """Vector of per-person monthly cost, escalated by mean tenure in state."""
    return base_cost * (1.0 + duration_multiplier_per_year * tenure_years)


def state_cost(base_cost, tenure_years, stocks, duration_multiplier_per_year):
    """Total monthly public cost across all states (excludes intervention spend)."""
    pp = per_person_monthly(base_cost, tenure_years, duration_multiplier_per_year)
    return float((pp * stocks).sum())
