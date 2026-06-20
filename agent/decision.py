"""DecisionAgent — the fourth agent: turns the simulator's numbers into a clear,
plain-English recommendation a non-technical director can act on.

The analyst agent runs the math and the viz agent draws it, but a budget director
reading "$5,024.3M (P50) vs $5,064.6M" can't tell what to *do*. This agent closes
that gap. It reads the already-computed scenarios and:

  * states the call — act now / you can wait — with a confidence on the DIRECTION
    (separate from the magnitude, which is always a planning estimate);
  * explains the number people misread: the 10-year baseline (~$5B) is mostly
    locked in no matter what; the timing decision moves a much smaller slice
    (the cost of waiting), and THAT is the number to look at;
  * names the break-even deadline in plain words.

It invents no figure — every number traces to the engine; Claude may only phrase it
(number-guarded), else a deterministic template is used.
"""

VERDICTS = {
    "act_now": "Act now",
    "lean_act_now": "Lean toward acting now",
    "can_wait": "Waiting is defensible here",
    "review": "Needs review",
}

# The chart that best argues each verdict (shown below the decision in the UI).
VERDICT_CHART = {
    "act_now": "cost_of_waiting",        # the waterfall: baseline + the waiting slice
    "lean_act_now": "scenario_costs",    # the delta bars + "range excludes $0" robustness
    "can_wait": "break_even_curve",      # how long you can safely wait
    "review": "sensitivity_tornado",     # what's fragile / worth tightening first
}
CHART_BLURB = {
    "cost_of_waiting": "the cost-of-waiting waterfall shows acting now's bill plus the slice you'd add by waiting.",
    "scenario_costs": "the delta chart shows each path's extra cost vs acting now, and whether it's real or noise.",
    "break_even_curve": "the break-even curve shows the last year you can safely wait.",
    "sensitivity_tornado": "the stress test shows which assumptions to tighten before committing.",
}


class DecisionAgent:
    def __init__(self, on_step=None):
        self._on_step = on_step
        self.trajectory = []

    def _step(self, skill, detail=""):
        step = {"skill": skill, "tier": 1, "approved": False}
        self.trajectory.append(step)
        if self._on_step is not None:
            try:
                self._on_step({**step, "label": "Synthesizing the recommendation",
                               "detail": detail or "Compare the futures, weigh the confidence",
                               "status": "running"})
            except Exception:
                pass

    def recommend(self, params, plan, runs, comparison, effect_band=None, direct=None):
        self._step("synthesize_decision")

        def usd(x):
            return f"${x/1e6:,.1f}M" if abs(x) < 1e9 else f"${x/1e9:,.1f}B"

        cow = comparison.get("cost_of_waiting") or {}
        sv = comparison.get("savings_vs_status_quo") or {}
        be = comparison.get("break_even") or {}
        delay = int(comparison.get("delay_years", plan.get("delay_years", 5)))

        cow_med = cow.get("extra_cost_median")
        cow_p10 = cow.get("extra_cost_p10")
        cow_p90 = cow.get("extra_cost_p90")
        save_med = sv.get("savings_median")
        be_year = be.get("break_even_year")
        baseline = (runs.get("status_quo") or {}).get("final_cum_cost_p50")

        # Direction robustness from the effect band (the model's weakest input).
        band = [effect_band.get(k) for k in ("cow_at_lo", "cow_base", "cow_at_hi")] if effect_band else []
        band = [v for v in band if v is not None]
        same_sign = bool(band) and (all(v > 0 for v in band) or all(v < 0 for v in band))

        # The verdict + how sure we are of the DIRECTION (not the dollar amount).
        if cow_med is None:
            verdict, direction_conf = "review", "low"
        elif cow_med > 0:
            if same_sign and cow_p10 is not None and cow_p10 > 0:
                verdict, direction_conf = "act_now", "high"
            elif same_sign:
                verdict, direction_conf = "act_now", "medium"
            else:
                verdict, direction_conf = "lean_act_now", "low"
        else:
            verdict, direction_conf = "can_wait", "medium"

        label = VERDICTS[verdict]

        # Plain-English headline + the slice-vs-baseline insight people misread.
        if cow_med is not None and cow_med > 0:
            tail = ("and that direction holds up even under pessimistic assumptions." if same_sign
                    else "though under less favourable assumptions the gap can shrink to nothing — so this "
                         "is a lean, not a sure thing.")
            headline = (f"{label} — waiting {delay} years is projected to cost about "
                        f"{usd(cow_med)} more, {tail}")
        elif cow_med is not None:
            headline = (f"{label} — at this budget, waiting {delay} years doesn't add a clear "
                        f"extra cost over acting now.")
        else:
            headline = f"{label} — the timing comparison needs a closer look."

        bullets = []
        if baseline is not None:
            bullets.append(
                f"**The big number is mostly locked in.** Homelessness here costs the public on the "
                f"order of {usd(baseline)} over 10 years *no matter what you do* — don't read that as "
                f"the decision.")
        if cow_med is not None:
            rng = (f" (it could be anywhere from {usd(cow_p10)} to {usd(cow_p90)})"
                   if cow_p10 is not None and cow_p90 is not None else "")
            bullets.append(
                f"**Your decision moves a smaller slice.** Acting now instead of waiting {delay} years "
                f"changes the cost by about {usd(cow_med)}{rng}. That slice is the number to watch.")
        if save_med is not None and save_med > 0:
            bullets.append(
                f"**Acting now also beats doing nothing** by roughly {usd(save_med)} over the horizon.")
        if band and same_sign:
            bullets.append(
                f"**The direction is reliable; the exact dollar figure is a planning estimate.** Even if "
                f"our assumptions about how well the programs work are off by half, waiting still costs "
                f"more — so the call is solid even though the precise amount is a range, not a promise.")
        elif band:
            bullets.append(
                f"**The direction is NOT certain — treat this as a lean.** Under less favourable "
                f"program-effect assumptions ({usd(min(band))} to {usd(max(band))} across the ±50% range), "
                f"the cost of waiting can fall to zero or flip. Acting now is the safer bet, but tighten "
                f"the intervention-effect estimates before committing.")
        if be_year:
            bullets.append(
                f"**You have a deadline.** Delaying past about year {be_year} wastes more than a full "
                f"year of program budget.")

        # The chart that argues the same case as the words (shown below the answer).
        rec_chart = VERDICT_CHART.get(verdict, "cost_of_waiting")
        bullets.append(f"**See it below — {CHART_BLURB[rec_chart]}**")

        plain_summary = headline + "\n\n" + "\n".join(f"- {b}" for b in bullets)

        decision = {
            "verdict": verdict,
            "verdict_label": label,
            "headline": headline,
            "plain_summary": plain_summary,
            "recommended_chart": rec_chart,
            "direction_confidence": direction_conf,
            "magnitude_note": ("The exact dollar figure depends on intervention-effect sizes "
                               "(the model's weakest input), so it is reported as a range, not a point."),
            "evidence": {
                "cost_of_waiting_musd": None if cow_med is None else round(cow_med / 1e6, 1),
                "cost_of_waiting_range_musd": (None if cow_p10 is None else
                                               [round(cow_p10 / 1e6, 1), round(cow_p90 / 1e6, 1)]),
                "savings_now_musd": None if save_med is None else round(save_med / 1e6, 1),
                "break_even_year": be_year,
                "baseline_10yr_musd": None if baseline is None else round(baseline / 1e6, 1),
                "delay_years": delay,
            },
            "trajectory": list(self.trajectory),
        }

        # `headline` is the single source of truth for the verdict sentence: it is
        # computed exactly once (above), shown verbatim on the Recommendation card,
        # and quoted verbatim by the brief (skills.verdict_citation). Claude may
        # rephrase the *bullets* in `plain_summary` below — it must never touch
        # `headline`, so the card and the brief can never disagree on the verdict.
        #
        # Optional Claude phrasing of the summary, number-guarded against ONLY the
        # figures above; on any unseen number we keep the deterministic template.
        try:
            from agent import planner
            allowed = "\n".join(str(v) for v in [
                usd(cow_med) if cow_med is not None else "",
                usd(cow_p10) if cow_p10 is not None else "",
                usd(cow_p90) if cow_p90 is not None else "",
                usd(save_med) if save_med is not None else "",
                usd(baseline) if baseline is not None else "",
                f"year {be_year}" if be_year else "", f"{delay} years", plain_summary,
            ])
            prompt = (
                "You are advising a city budget director who is NOT technical. In <=130 words of "
                "markdown, give a clear recommendation from the facts below. Lead with the call "
                "(act now / wait). Make the key point that the multi-billion-dollar baseline is mostly "
                "unavoidable and the timing decision only moves the smaller 'cost of waiting' slice. Use "
                "ONLY the dollar figures present in the facts; do not invent or recompute any number.\n\n"
                "FACTS:\n" + allowed)
            narrated = planner.narrate_grounded(prompt, allowed)
            if narrated:
                decision["plain_summary"] = narrated
                decision["narrated_by"] = "claude"
        except Exception:
            pass

        return decision
