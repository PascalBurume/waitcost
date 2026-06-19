"""Equity / disparity lens — who bears homelessness, and who is most exposed.

The responsible-AI differentiator: it analyzes disparities at the POPULATION
level (which groups are over-represented, who is most unsheltered) WITHOUT
profiling any individual — the opposite of person-level predictive tools whose
central problem is racial bias. All numbers are real and CSV-driven:

  * data/equity_race.csv        homeless population by race -> HUD 2024 PIT CoC PopSub
  * data/equity_pop_shares.csv  general population shares    -> US Census ACS

Two metrics a decision-maker needs:
  1. Disproportionality = (group's share of the homeless) / (its share of the
     population). >1 = over-represented; surfaces structural inequity.
  2. Unsheltered rate by group = who is most exposed to the highest-cost state.

To add a city: append its 7 race rows (from the HUD PopSub race table) to
equity_race.csv and its population shares to equity_pop_shares.csv. Nothing else.
"""
import csv
import os

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RACE_CSV = os.path.join(_REPO, "data", "equity_race.csv")
_POP_CSV = os.path.join(_REPO, "data", "equity_pop_shares.csv")
# friendly names for the cities we carry equity data for
_NAMES = {
    "CA-600": "Los Angeles City & County", "CA-503": "Sacramento City & County",
    "AZ-501": "Tucson/Pima County", "CA-601": "San Diego City and County",
    "CA-501": "San Francisco", "WA-500": "Seattle/King County",
    "AZ-502": "Phoenix/Mesa/Maricopa County", "CA-500": "San Jose/Santa Clara",
    "OR-501": "Portland/Multnomah County", "NV-500": "Las Vegas/Clark County",
    "NY-600": "New York City", "DC-500": "District of Columbia",
    "MN-500": "Minneapolis/Hennepin County", "TN-502": "Knoxville/Knox County",
    "FL-600": "Miami-Dade County", "PA-500": "Philadelphia", "IL-510": "Chicago",
}


def _load():
    race = {}
    with open(_RACE_CSV) as f:
        for r in csv.DictReader(f):
            race.setdefault(r["coc"], {})[r["group"]] = {
                "total": int(r["total"]), "unsheltered": int(r["unsheltered"])}
    pop = {}
    if os.path.exists(_POP_CSV):
        with open(_POP_CSV) as f:
            for r in csv.DictReader(f):
                pop.setdefault(r["coc"], {})[r["group"]] = float(r["pop_share_pct"])
    return race, pop


_RACE, _POP = _load()


def available_equity_cocs():
    return sorted(_RACE.keys())


def equity_analysis(coc="CA-600"):
    by_race = _RACE.get(coc)
    if not by_race:
        raise ValueError(f"No equity data loaded for '{coc}'. Loaded: {available_equity_cocs()}. "
                         "Add it from that CoC's HUD PopSub race table.")
    pop_share = _POP.get(coc, {})
    total_homeless = sum(v["total"] for v in by_race.values())
    groups = []
    for g, v in by_race.items():
        h_share = v["total"] / total_homeless * 100.0
        p_share = pop_share.get(g, 0.0)
        groups.append({
            "group": g, "homeless_share_pct": round(h_share, 1),
            "population_share_pct": p_share,
            "disproportionality": round(h_share / p_share, 2) if p_share else None,
            "unsheltered_rate_pct": round(v["unsheltered"] / v["total"] * 100.0, 1) if v["total"] else 0.0,
        })
    over = [g for g in groups if g["disproportionality"]]
    top = max(over, key=lambda g: g["disproportionality"]) if over else None
    return {"coc": coc, "name": _NAMES.get(coc, coc), "homeless_total": total_homeless,
            "groups": sorted(groups, key=lambda g: g["disproportionality"] or 0, reverse=True),
            "most_overrepresented": ({"group": top["group"], "factor": top["disproportionality"]}
                                     if top else None),
            "source": "Homeless by race: HUD 2024 PIT CoC PopSub. Population shares: US Census ACS."}


def headline(coc="CA-600"):
    a = equity_analysis(coc)
    m = a["most_overrepresented"]
    if not m:
        return (f"**Equity — {a['name']}**: composition and unsheltered-rate by race are available; "
                f"the over-representation ratio is pending this city's population race shares.")
    return (f"**Equity — {a['name']}**: **{m['group']} residents are {m['factor']}x over-represented** "
            f"among people experiencing homelessness (share of homeless vs. share of population). "
            f"This is structural inequity the budget choice should weigh; the tool surfaces it at the "
            f"population level and never profiles individuals. Source: HUD 2024 PIT + Census ACS.")
