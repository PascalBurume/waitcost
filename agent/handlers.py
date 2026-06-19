"""Intent handlers — one function per answerable intent.

These are the bodies that used to live in the if/elif chain of
`WaitCostAgent._direct_answer`. Each is now a small, independently testable
function taking a single `AnswerContext`. The orchestrator builds the context
once (the fixed pipeline already computed everything) and dispatches via the
capability registry, so adding an intent no longer means editing the loop.

Behaviour is preserved exactly: handlers that touch extra Tier-1 skills
(`regional`, `compare_budgets`, `compare_mix`, `equity`, `city_context`) call
`ctx.agent._check_tier(...)` first, exactly as the original branches did.
"""
import re
from dataclasses import dataclass
from typing import Optional

from agent import skills
from analysis import metrics


@dataclass
class AnswerContext:
    params: dict
    plan: dict
    runs: dict
    comparison: dict
    drivers: list
    backtest: Optional[dict] = None
    effect_band: Optional[dict] = None
    agent: object = None          # the WaitCostAgent, for _check_tier on extra skills

    @property
    def horizon_years(self) -> int:
        return int(self.params["meta"]["horizon_months"] // 12)


def _usd(x):
    return f"${x/1e6:,.1f}M"


def _coc(params):
    m = re.search(r"([A-Z]{2}-\d{3})", params["meta"].get("coc", ""))
    return m.group(1) if m else "CA-600"


# --- handlers (intent -> headline string) ----------------------------------
def roi(ctx: AnswerContext):
    p, plan, comparison, hy = ctx.params, ctx.plan, ctx.comparison, ctx.horizon_years
    sv = comparison.get("savings_vs_status_quo")
    budget = float(plan.get("budget_musd", p["meta"].get("default_budget_musd", 10.0)))
    spend = budget * 1e6 * hy
    ratio = metrics.benefit_cost_ratio(sv["savings_median"], spend) if sv else None
    if ratio is not None and ratio > 0:
        lo = metrics.benefit_cost_ratio(sv["savings_p10"], spend)
        hi = metrics.benefit_cost_ratio(sv["savings_p90"], spend)
        band = (f" (80% range {lo:.1f}–{hi:.1f})" if lo is not None and hi is not None else "")
        return (f"**Every $1 invested now returns about ${ratio:.1f}** in avoided public cost "
                f"over {hy} years at ${budget:.0f}M/yr{band}.")
    return (f"**At ${budget:.0f}M/yr the program does not pay back over {hy} years** "
            f"at this city's scale (benefit-cost ratio below 1). Try a smaller budget or compare "
            f"budgets to find where the return turns positive.")


def cost_per_person(ctx: AnswerContext):
    runs, comparison, hy = ctx.runs, ctx.comparison, ctx.horizon_years
    sq = runs["status_quo"]["final_active_homeless"]
    now = runs["act_now"]["final_active_homeless"]
    helped = sq - now
    sv = comparison.get("savings_vs_status_quo")
    if helped > 0 and sv:
        per = sv["savings_median"] / helped
        return (f"**Acting now means about {helped:,.0f} fewer people homeless at the "
                f"{hy}-year horizon** ({sq:,.0f} → {now:,.0f}), and avoids roughly "
                f"${per/1e3:,.0f}k of public cost per person helped.")
    return (f"**At this budget, acting now doesn't measurably reduce the {hy}-year "
            f"homeless count** ({sq:,.0f} → {now:,.0f}). Try a larger budget or a different mix.")


def uncertainty(ctx: AnswerContext):
    comparison, drivers = ctx.comparison, ctx.drivers
    cow = comparison.get("cost_of_waiting")
    parts = []
    if cow and cow["extra_cost_median"]:
        width = (cow["extra_cost_p90"] - cow["extra_cost_p10"]) / abs(cow["extra_cost_median"]) * 100
        parts.append(f"the 80% range spans about {width:.0f}% of the median ("
                     f"{_usd(cow['extra_cost_p10'])} – {_usd(cow['extra_cost_p90'])})")
    if ctx.effect_band:
        parts.append(f"most of that swing is the (low-confidence) intervention-effect sizes — "
                     f"at ±50% the cost-of-waiting ranges {_usd(ctx.effect_band['cow_at_lo'])} – "
                     f"{_usd(ctx.effect_band['cow_at_hi'])}")
    if drivers:
        parts.append(f"the most influential assumption is '{drivers[0]['driver']}' "
                     f"(confidence {drivers[0]['confidence']})")
    if ctx.backtest:
        parts.append(f"and the model backtests to within ~{ctx.backtest['abs_pct_error_p50']:.0f}% "
                     f"of the observed 2024 count")
    if parts:
        return ("**Here's how confident the number is:** " + "; ".join(parts) +
                ". The sign (waiting costs more) is robust; the magnitude is a planning range.")
    return None


def regional(ctx: AnswerContext):
    p, plan = ctx.params, ctx.plan
    ctx.agent._check_tier("regional_cost_of_waiting")
    budget = float(plan.get("budget_musd", p["meta"].get("default_budget_musd", 10.0)))
    delay = int(plan.get("delay_years", 5)) or 5
    reg = skills.regional_cost_of_waiting(budget, delay)
    top = reg["cities"][:5]
    rows = " · ".join(f"{r['coc']} {_usd(r['cost_of_waiting_musd']*1e6)}" for r in top)
    lead = top[0] if top else None
    return (f"**Across {len(reg['cities'])} cities, waiting {delay} years costs the most in "
            f"{lead['name']}** (about {_usd(lead['cost_of_waiting_musd']*1e6)} at ${budget:.0f}M/yr). "
            f"Ranked cost of waiting: {rows}." if lead else
            "Regional ranking is unavailable right now.")


def break_even(ctx: AnswerContext):
    be = (ctx.comparison.get("break_even") or {}).get("break_even_year")
    if be:
        return (f"**Break-even is about year {be}.** Delaying past year {be} wastes more "
                f"than one full year of program budget — that's when waiting stops paying off.")
    return ("**No break-even within 10 years** at this budget — the extra cost of delay "
            "stays below one year of program budget across the scanned window.")


def savings_now(ctx: AnswerContext):
    sv = ctx.comparison.get("savings_vs_status_quo")
    if sv:
        m = sv["savings_median"]
        if m >= 0:
            return (f"**Acting now saves about {_usd(m)}** over 10 years vs. doing nothing "
                    f"(80% range {_usd(sv['savings_p10'])} – {_usd(sv['savings_p90'])}).")
        return (f"**At this budget, acting now costs about {_usd(-m)} more than doing nothing** "
                f"over 10 years — at this city's scale the program doesn't pay back. Try a "
                f"smaller budget or compare budgets to find where it does.")
    return None


def outcome_at_horizon(ctx: AnswerContext):
    sq = ctx.runs["status_quo"]["final_active_homeless"]
    now = ctx.runs["act_now"]["final_active_homeless"]
    return (f"**If nothing changes, about {sq:,.0f} people are homeless at the 10-year "
            f"horizon.** Acting now brings that to about {now:,.0f} (~{sq-now:,.0f} fewer).")


def sensitivity(ctx: AnswerContext):
    drivers = ctx.drivers
    if drivers:
        d = drivers[0]
        return (f"**The result is most sensitive to '{d['driver']}'** — a +20% change moves "
                f"the 10-year cost by {d['pct_change']:+.1f}% (confidence {d['confidence']}). "
                f"That's the assumption to tighten with data first.")
    return None


def compare_budgets(ctx: AnswerContext):
    p, plan = ctx.params, ctx.plan
    budgets = plan.get("budgets") or [15.0, 50.0, 100.0]
    ctx.agent._check_tier("compare_budgets")
    cb = skills.compare_budgets(p, budgets, delay=plan.get("delay_years", 0))
    rows = " · ".join(f"${r['budget_musd']:.0f}M → {_usd(r['cum_cost_p50'])}" for r in cb["budgets"])
    return (f"**Lowest 10-year public cost at ${cb['best_budget_musd']:.0f}M/yr.** "
            f"10-year cost (P50) by budget: {rows}.")


def compare_mix(ctx: AnswerContext):
    p, plan = ctx.params, ctx.plan
    ctx.agent._check_tier("compare_mix")
    cm = skills.compare_mix(p, plan.get("budget_musd", 50.0), delay=plan.get("delay_years", 0))
    rows = " · ".join(f"{r['mix']} → {_usd(r['cum_cost_p50'])}" for r in cm["mixes"])
    return (f"**A '{cm['best_mix']}' mix gives the lowest 10-year cost** at "
            f"${cm['budget_musd']:.0f}M/yr. 10-year cost (P50) by mix: {rows}.")


def equity(ctx: AnswerContext):
    coc = _coc(ctx.params)
    ctx.agent._check_tier("equity_analysis")
    try:
        from analysis.equity import headline
        return headline(coc)
    except Exception:
        return ("Equity disparity data is loaded for Los Angeles (CA-600) today; other "
                "cities are pending their HUD PopSub race table (same process to add). "
                "Switch to Los Angeles to see the racial-disparity analysis.")


def city_context(ctx: AnswerContext):
    ctx.agent._check_tier("retrieve_us_context")
    ctx_data = skills.retrieve_us_context(_coc(ctx.params))
    i = ctx_data["indicators"]
    return (f"**{ctx_data['name']}** — about **{i['homeless_pit_total']:,} people homeless** "
            f"({i['homeless_rate_per_1k']}/1,000 residents; {i['unsheltered_share_pct']}% "
            f"unsheltered, {i['chronic_share_pct']}% chronic). Housing is costly vs. incomes: "
            f"median home value ${i['median_home_value_usd']:,} vs median household income "
            f"${i['median_household_income_usd']:,} (ratio {i['home_value_to_income_ratio']}x); "
            f"poverty {i['poverty_rate_pct']}%. Source: real HUD 2024 PIT + Census ACS 2024.")


def cost_of_waiting(ctx: AnswerContext):
    """The default headline."""
    cow = ctx.comparison.get("cost_of_waiting")
    if cow:
        return (f"**Waiting {ctx.comparison.get('delay_years', ctx.plan.get('delay_years'))} years costs "
                f"about {_usd(cow['extra_cost_median'])} more** over 10 years "
                f"(80% range {_usd(cow['extra_cost_p10'])} – {_usd(cow['extra_cost_p90'])}).")
    return None
