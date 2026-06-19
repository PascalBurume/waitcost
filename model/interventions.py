"""Map intervention spend to additive transition-rate bonuses."""


def intervention_bonus(params, scenario, month):
    """Return {(from, to): added_monthly_rate} for the active interventions."""
    bonus = {}
    if not scenario.active(month):
        return bonus
    for name, cfg in params["interventions"].items():
        musd = scenario.annual_budget_musd * scenario.mix.get(name, 0.0)
        added = cfg["effect_per_million_per_month"] * musd
        key = (cfg["target"]["from"], cfg["target"]["to"])
        bonus[key] = bonus.get(key, 0.0) + added
    return bonus
