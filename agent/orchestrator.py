"""WaitCost agent: the 3-stage loop, MEMORY.md persistence, and Action Tiers.

Stages (OpenClaw pattern): data acquisition -> processing/reasoning -> output.
Tier 0-1 actions run automatically; Tier 2+ (e.g. recommending an allocation)
require explicit human approval — the human-in-the-loop gate.
"""
import datetime
import re
from pathlib import Path

from agent import skills, planner, handlers, capabilities

ACTION_TIERS = {
    "fetch_hud_data": 0,
    "check_data_support": 0,
    "retrieve_us_context": 0,
    "equity_analysis": 0,
    "load_city_sources": 0,
    "route_city_brief": 0,
    "load_inflow_model": 0,
    "sensitivity_report": 0,
    "run_simulation": 1,
    "synthesize_decision": 1,
    "compare_scenarios": 1,
    "run_backtest": 1,
    "effect_sensitivity": 1,
    "compare_budgets": 1,
    "compare_mix": 1,
    "regional_cost_of_waiting": 1,
    "write_brief": 1,
    "optimize_allocation": 2,   # recommends an allocation -> needs approval
}

# Human-readable presentation for each skill, so the streamed trajectory reads
# like a reasoning timeline (not raw function names). label · one-line detail.
SKILL_PRESENTATION = {
    "fetch_hud_data": ("Loading HUD data", "Real 2024 PIT counts + Census ACS signals"),
    "check_data_support": ("Checking data sufficiency", "Decline rather than show unsupported bands"),
    "retrieve_us_context": ("Retrieving city context", "HUD PIT + Census ACS indicators"),
    "equity_analysis": ("Equity analysis", "Population-level racial disparities (no profiling)"),
    "load_city_sources": ("Loading city source registry", "Curated lead agency + care plan + citations"),
    "route_city_brief": ("Routing to City Brief agent", "Grounded context — not the cost model"),
    "load_inflow_model": ("Loading learned inflow model", "ACS→PIT Ridge model + exact SHAP"),
    "run_simulation": ("Running a scenario (Monte Carlo)", "Status quo · act now · delay"),
    "synthesize_decision": ("Synthesizing the recommendation", "Turn the numbers into a plain-English call"),
    "compare_scenarios": ("Comparing scenarios", "Cost of waiting · savings · break-even"),
    "sensitivity_report": ("Ranking assumption drivers", "Which rate moves the result most (XAI)"),
    "run_backtest": ("Backtesting against observed 2024", "Seed real 2023 PIT, predict 2024"),
    "effect_sensitivity": ("Stress-testing effect sizes", "Headline under ±50% intervention effects"),
    "compare_budgets": ("Comparing budgets", "10-yr cost across candidate budgets"),
    "compare_mix": ("Comparing intervention mixes", "Prevention · rapid-rehousing · supportive"),
    "regional_cost_of_waiting": ("Ranking cities by cost of waiting", "Same engine across multiple CoCs"),
    "write_brief": ("Writing decision brief", "Narrative memo + JSON + CSV artifacts"),
    "optimize_allocation": ("Recommending an allocation", "Tier 2 — requires human approval"),
}


class TierViolation(RuntimeError):
    pass


def _fmt_usd(x):
    return f"${x/1e6:,.1f}M"


def _synthesize_sweep(intent, per_call, plan):
    """Fold several single-budget call results into ONE answer (the executor's
    synthesizer). Every budget appears — the no-silent-drop guarantee surfaces as
    a visible per-budget row, never a quietly chosen subset. The figures are the
    same the engine computes for each budget alone, so they match a single-budget
    /ask exactly."""
    if intent == "cost_of_waiting":
        rows = []
        for pc in per_call:
            cow = pc.get("cow")
            if not cow:
                continue
            rows.append(f"- **${pc['budget_musd']:,.0f}M/yr** → about {_fmt_usd(cow['extra_cost_median'])} "
                        f"more (80% range {_fmt_usd(cow['extra_cost_p10'])} – {_fmt_usd(cow['extra_cost_p90'])})")
        return (f"**Waiting {plan['delay_years']} years — cost of waiting by program size:**\n"
                + "\n".join(rows)
                + "\n\nThe direction (waiting costs more) holds at every budget; the magnitude scales "
                  "with program size.")
    # Generic fold for other single-budget intents: label each call's headline.
    rows = [f"- **${pc['budget_musd']:,.0f}M/yr** — {pc['headline']}"
            for pc in per_call if pc.get("headline")]
    return "**Answered for each budget:**\n" + "\n".join(rows)


def _coc_code(raw):
    """Pull a CoC code (e.g. 'CA-600') out of the params meta coc string."""
    m = re.search(r"([A-Z]{2}-\d{3})", raw or "")
    return m.group(1) if m else "CA-600"


def _brief_to_markdown(brief):
    """Render a city brief as a self-contained markdown block for /ask consumers.
    Carries the 'general context' label, the situation, the plan, and clickable sources."""
    lines = [f"_{brief['label']}_", "", f"## {brief.get('city', brief['coc'])} — homelessness brief", ""]
    if brief.get("lead_agency"):
        lines.append(f"**Lead agency:** {brief['lead_agency']}")
    plan = brief.get("plan") or {}
    if plan.get("title"):
        title = f"[{plan['title']}]({plan['url']})" if plan.get("url") else plan["title"]
        lines.append(f"**Care plan:** {title}")
    lines += ["", brief.get("situation", ""), ""]
    if plan.get("summary"):
        lines += ["**Strategy.** " + plan["summary"], ""]
    if brief.get("national_context"):
        lines += [brief["national_context"], ""]
    if brief.get("sources"):
        lines.append("**Sources**")
        lines += [f"- [{s['title']}]({s['url']})" for s in brief["sources"]]
    return "\n".join(lines).strip()


class WaitCostAgent:
    def __init__(self, params_path, memory_path="MEMORY.md", max_auto_tier=1, params=None):
        self.params_path = params_path
        self.memory_path = Path(memory_path)
        self.max_auto_tier = max_auto_tier
        self._params_override = params   # prebuilt params dict (e.g. another CoC)
        self.trajectory = []     # recorded steps (the evaluation artifact)
        self._on_step = None     # optional streaming callback (set in answer())

    # --- memory + tier guards ------------------------------------------------
    def _check_tier(self, skill, approve=False, detail=None):
        tier = ACTION_TIERS.get(skill, 0)
        if tier > self.max_auto_tier and not approve:
            raise TierViolation(
                f"Skill '{skill}' is Action Tier {tier} (human approval required).")
        # `detail` distinguishes repeated calls of the same skill — e.g. the three
        # Monte-Carlo runs (status quo / act now / delay) that otherwise look identical.
        step = {"skill": skill, "tier": tier, "approved": approve}
        if detail:
            step["detail"] = detail
        self.trajectory.append(step)
        # Stream this step as it executes (feature ①). Presentation map turns the
        # raw skill name into a readable label + detail; a Tier-2 step is flagged.
        if self._on_step is not None:
            label, default_detail = SKILL_PRESENTATION.get(skill, (skill, ""))
            status = "approved" if (tier == 2 and approve) else "running"
            try:
                self._on_step({**step, "label": label, "detail": detail or default_detail, "status": status})
            except Exception:
                pass   # a broken consumer must never break the agent loop

    def _remember(self, text):
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        with open(self.memory_path, "a") as f:
            f.write(f"\n- [{stamp}] {text}")

    # --- intent -> tailored direct answer ------------------------------------
    def _direct_answer(self, params, plan, runs, comparison, drivers,
                       backtest=None, effect_band=None):
        """Dispatch to the intent's handler via the capability registry. The
        per-intent bodies now live in agent/handlers.py; this just builds the
        context (the fixed pipeline already computed everything) and routes."""
        ctx = handlers.AnswerContext(
            params=params, plan=plan, runs=runs, comparison=comparison, drivers=drivers,
            backtest=backtest, effect_band=effect_band, agent=self)
        cap = capabilities.by_intent(plan.get("intent", "cost_of_waiting"))
        handler = cap.handler if (cap and cap.handler) else \
            capabilities.by_intent("cost_of_waiting").handler
        return handler(ctx)

    # --- facts handed to Gemma for the narrated brief (feature ③) -----------
    def _brief_facts(self, question, params, runs, comparison, drivers,
                     inflow_model, backtest, intent, direct):
        """Compact dict of ALREADY-COMPUTED figures. This doubles as the whitelist
        of numbers Gemma is allowed to echo (the number guard rejects anything else)."""
        def usd(x):
            return f"${x/1e6:,.1f}M"

        facts = {
            "question": question,
            "city": params["meta"]["coc"],
            "intent": intent,
        }
        cow = comparison.get("cost_of_waiting")
        if cow:
            facts["cost_of_waiting_median"] = usd(cow["extra_cost_median"])
            facts["cost_of_waiting_80pct_range"] = (
                f"{usd(cow['extra_cost_p10'])} to {usd(cow['extra_cost_p90'])}")
            facts["delay_years"] = comparison.get("delay_years")
        if "status_quo" in runs:
            facts["status_quo_10yr_cost"] = usd(runs["status_quo"]["final_cum_cost_p50"])
        if "act_now" in runs:
            facts["act_now_10yr_cost"] = usd(runs["act_now"]["final_cum_cost_p50"])
        sv = comparison.get("savings_vs_status_quo")
        if sv:
            facts["savings_acting_now"] = usd(sv["savings_median"])
        if drivers:
            facts["top_assumption_driver"] = drivers[0]["driver"]
            facts["top_driver_pct_change"] = f"{drivers[0]['pct_change']:+.1f}%"
        if inflow_model and inflow_model.get("shap_target"):
            facts["top_shap_driver"] = inflow_model["shap_target"][0]["feature"]
        if backtest:
            facts["backtest_central_error"] = f"{backtest['abs_pct_error_p50']:.0f}%"
        if direct:
            facts["headline_one_liner"] = direct
        facts["disclaimer"] = ("This tool informs a budget-timing tradeoff; it does not decide "
                               "allocations or forecast individuals. All figures are ranges.")
        return facts

    # --- the agent loop ------------------------------------------------------
    def answer(self, question, out_dir="outputs", approve_allocation=False, on_step=None):
        self._on_step = on_step   # feature ①: stream each step as it runs
        # STAGE 1 — data acquisition
        self._check_tier("fetch_hud_data")
        params = self._params_override or skills.fetch_hud_data(self.params_path)

        # Bypass condition (GOVERNANCE.md): decline rather than show unsupported bands.
        self._check_tier("check_data_support")
        try:
            skills.check_data_support(params)
        except skills.DataSufficiencyError as e:
            self._remember(f"DECLINED (bypass): {e} | Q='{question}'")
            return {"declined": True, "reason": str(e),
                    "coc": params.get("meta", {}).get("coc"), "trajectory": self.trajectory}

        self._check_tier("load_inflow_model")
        inflow_model = skills.load_inflow_model()   # learned component (metrics+SHAP)
        the_plan = planner.plan(question, params)

        # Greeting / meta ("hi", "what can you do?") OR an in-scope question the
        # engine can't map (clarify): return a warm orientation immediately — never
        # run the engine. Reuses the declined render path (declined=True) flagged
        # greeting=True so the UI welcomes/guides rather than refuses.
        if the_plan.get("intent") in ("greeting", "clarify"):
            kind = the_plan["intent"]
            self._remember(f"{kind.upper()}: Q='{question}'")
            if kind == "clarify":
                reason = ("I'm not sure which analysis you're after. I can estimate the cost of "
                          "waiting, break-even timing, savings from acting now, ROI, cost per person "
                          "helped, outcomes at the horizon, budget/mix comparisons, equity, or rank "
                          "the cost of inaction across cities. Which would you like?")
            else:
                reason = ("Hi! I'm WaitCost — I estimate the public cost of delaying homelessness "
                          "intervention in a city. Ask me about the cost of waiting, break-even timing, "
                          "savings from acting now, ROI, cost per person, outcomes at the 10-year "
                          "horizon, or budget/mix comparisons.")
            return {"declined": True, "greeting": True, "intent": kind, "plan": the_plan,
                    "reason": reason, "trajectory": self.trajectory}

        # Scope check: decline questions the city-level engine cannot truthfully answer.
        if the_plan.get("intent") == "out_of_scope":
            self._remember(f"DECLINED (out of scope): Q='{question}'")
            return {"declined": True, "out_of_scope": True, "plan": the_plan,
                    "reason": ("This tool answers CoC-level budget-timing questions — cost of "
                               "waiting, break-even, savings, outcomes, and budget/mix comparisons. "
                               "It cannot answer questions about specific individuals or sub-CoC "
                               "geographies."),
                    "trajectory": self.trajectory}

        # City Brief hand-off: qualitative/contextual questions (the city's situation
        # or its care plan/strategy) are answered by the THIRD agent, the CityBriefAgent,
        # from grounded sources — NOT the cost simulator. Single front door (/ask), but
        # this branch delegates and returns a labelled brief instead of running the engine.
        if the_plan.get("intent") in ("city_situation", "care_plan"):
            self._check_tier("route_city_brief")    # streams "Routing to City Brief agent"
            from agent.city_brief import CityBriefAgent
            cb = CityBriefAgent(memory_path=self.memory_path, on_step=self._on_step)
            coc = _coc_code(params["meta"].get("coc", "CA-600"))
            city_brief = cb.brief(coc, question=question)
            self._remember(f"ROUTED to CityBrief: intent={the_plan['intent']} | coc={coc} | Q='{question}'")
            return {
                "declined": False, "city_brief": city_brief, "intent": the_plan["intent"],
                "plan": the_plan, "direct_answer": city_brief["situation"],
                "recommended_chart": "city_benchmark",
                "brief_markdown": _brief_to_markdown(city_brief),
                "label": city_brief["label"], "online": city_brief["online"],
                "trajectory": self.trajectory + city_brief["trajectory"],
            }

        # Retrieval tools (kind=retrieval): definitional / data-provenance questions
        # are answered from cited local sources — NOT the cost engine. Like the City
        # Brief branch, this returns a labelled, sourced answer without simulating.
        if the_plan.get("intent") in ("concept_qa", "data_lookup"):
            from agent import retrieval
            self._check_tier("route_city_brief")   # streams a "grounded context" step
            fn = retrieval.concept_qa if the_plan["intent"] == "concept_qa" else retrieval.data_lookup
            r = fn(question, params)
            src_md = "".join(f"\n- [{s['title']}]({s['url']})" for s in r.get("sources", []))
            brief_md = f"_{r['label']}_\n\n{r['answer']}" + (f"\n\n**Sources**{src_md}" if src_md else "")
            self._remember(f"RETRIEVAL {the_plan['intent']}: Q='{question}' | sources={len(r.get('sources', []))}")
            return {
                "declined": False, "intent": the_plan["intent"], "plan": the_plan,
                "direct_answer": r["answer"], "recommended_chart": None,
                "brief_markdown": brief_md, "sources": r.get("sources", []),
                "label": r["label"], "trajectory": self.trajectory,
            }

        # STAGE 2 — processing / reasoning
        budget = the_plan["budget_musd"]
        mix = the_plan.get("mix")
        scenario_objs = {
            "status_quo": skills.make_scenario(params, "Status quo (no new intervention)", budget=0.0),
            "act_now": skills.make_scenario(params, "Act now", delay=0, budget=budget, mix=mix),
            "delay": skills.make_scenario(
                params, f"Delay {the_plan['delay_years']} years",
                delay=the_plan["delay_years"], budget=budget, mix=mix),
        }
        # Three futures, one engine: simulate "do nothing", "act now", and "wait N
        # years". Each is its own Monte-Carlo run — that's why the timeline shows the
        # step three times (not a bug): the comparison BETWEEN them is the decision.
        run_detail = {
            "status_quo": "Future 1 of 3 · do nothing",
            "act_now": "Future 2 of 3 · act now",
            "delay": f"Future 3 of 3 · wait {the_plan['delay_years']} years",
        }
        runs = {}
        for key, sc in scenario_objs.items():
            self._check_tier("run_simulation", detail=run_detail.get(key))
            runs[key] = skills.run_simulation(params, sc)

        self._check_tier("compare_scenarios")
        comparison = skills.compare_scenarios(params, the_plan, runs)

        self._check_tier("sensitivity_report")
        drivers = skills.sensitivity_report(params, scenario_objs["act_now"])

        self._check_tier("run_backtest")
        backtest = skills.run_backtest(params)            # face validity vs observed 2024

        self._check_tier("effect_sensitivity")
        effect_band = skills.effect_sensitivity(params, the_plan)  # headline under +/-50% effects

        # Tier 2: only if a human approved an allocation recommendation
        if approve_allocation:
            self._check_tier("optimize_allocation", approve=True)
            self._remember("Human approved Tier-2 allocation recommendation step.")

        # Intent-specific direct answer (routes the question to the right computation).
        intent = the_plan.get("intent", "cost_of_waiting")
        direct = self._direct_answer(params, the_plan, runs, comparison, drivers,
                                     backtest=backtest, effect_band=effect_band)

        # Executor: a compound question (e.g. "$1M and $15M") is a LIST of calls. The
        # primary call drove the full pipeline above; here we run the EXTRA calls
        # (same engine tool, different budget) and the synthesizer folds them into one
        # answer. status_quo is budget-independent, so it's reused (not recomputed).
        # Single-call questions skip this entirely (calls[1:] is empty) — byte-identical.
        sweep = None
        extra_calls = (the_plan.get("calls") or [])[1:]
        cap = capabilities.by_intent(intent)
        if extra_calls and cap and cap.runs_engine and cap.handler:
            per_call = [{"budget_musd": budget, "cow": comparison.get("cost_of_waiting"),
                         "headline": direct}]
            for call in extra_calls:
                cargs = call.get("args", {})
                cb = float(cargs.get("budget_musd", budget))
                cd = int(cargs.get("delay_years", the_plan["delay_years"]))
                c_runs = {"status_quo": runs["status_quo"]}
                c_scen = {
                    "act_now": skills.make_scenario(params, "Act now", delay=0, budget=cb, mix=mix),
                    "delay": skills.make_scenario(params, f"Delay {cd} years", delay=cd, budget=cb, mix=mix),
                }
                for key, sc in c_scen.items():
                    self._check_tier("run_simulation", detail=f"call · ${cb:,.0f}M/yr")
                    c_runs[key] = skills.run_simulation(params, sc)
                c_plan = {**the_plan, "budget_musd": cb, "delay_years": cd}
                c_comparison = skills.compare_scenarios(params, c_plan, c_runs)
                c_ctx = handlers.AnswerContext(
                    params=params, plan=c_plan, runs=c_runs, comparison=c_comparison,
                    drivers=drivers, backtest=backtest, effect_band=effect_band, agent=self)
                per_call.append({"budget_musd": cb,
                                 "cow": c_comparison.get("cost_of_waiting"),
                                 "headline": cap.handler(c_ctx)})
            direct = _synthesize_sweep(intent, per_call, the_plan)
            sweep = {"intent": intent, "delay_years": the_plan["delay_years"],
                     "rows": [{"budget_musd": pc["budget_musd"], "cost_of_waiting": pc.get("cow")}
                              for pc in per_call]}

        # No-silent-drop: surface any coverage note from the normalizer in the answer.
        for note in (the_plan.get("coverage_notes") or []):
            if note and note not in direct:
                direct = f"{direct}\n\n_{note}_"

        # The decision agent turns the raw scenario numbers into a plain-English
        # recommendation a non-technical director can act on (act now / wait, with a
        # confidence on the DIRECTION and the baseline-vs-slice framing).
        self._check_tier("synthesize_decision")
        from agent.decision import DecisionAgent
        decision = DecisionAgent(on_step=self._on_step).recommend(
            params, the_plan, runs, comparison, effect_band=effect_band, direct=direct)

        # The visualization agent recommends the right chart for this question.
        from analysis.viz import VizAgent
        recommended_chart = VizAgent().recommend(intent)
        # For the generic cost-of-waiting question, let the decision agent's chart
        # (which argues its verdict) win — but never override intent-specific bindings
        # like regional/compare_mix/equity.
        if intent == "cost_of_waiting" and decision.get("recommended_chart"):
            recommended_chart = decision["recommended_chart"]
        # A budget sweep states cost-of-waiting PER budget, so the chart must show
        # that quantity per budget (not the single-budget waterfall) — keeps the
        # chart-matches-answer invariant.
        if sweep and intent == "cost_of_waiting":
            recommended_chart = "cost_of_waiting_by_budget"

        # STAGE 3 — output generation
        self._check_tier("write_brief")
        brief = skills.write_brief(question, params, runs, comparison, drivers, out_dir,
                                   inflow_model=inflow_model, backtest=backtest,
                                   effect_band=effect_band, intent=intent, direct_answer=direct,
                                   decision=decision)

        # Feature ③: let local Gemma WRITE the memo from the engine's numbers.
        # Every figure is number-guarded inside narrate_brief; on None we keep the
        # deterministic markdown. brief_author records which one the user sees.
        brief_markdown = brief["brief_markdown"]
        brief_author = "deterministic"
        facts = self._brief_facts(question, params, runs, comparison, drivers,
                                  inflow_model, backtest, intent, direct)
        gemma_memo = planner.narrate_brief(facts)
        if gemma_memo:
            brief_markdown = gemma_memo
            brief_author = "gemma"

        # Single source of truth, whichever author wrote the body: the verdict
        # sentence is the decision agent's headline, cited verbatim. The
        # deterministic brief already embeds it; a Gemma memo writes prose AROUND
        # the verdict but must never become the verdict — so if the citation is
        # absent (Gemma path) we prepend it. The framing string is the idempotency
        # sentinel, so the deterministic path is never double-prepended.
        if decision and skills.RECOMMENDATION_FRAMING not in brief_markdown:
            brief_markdown = "\n".join(skills.verdict_citation(decision)) + "\n\n" + brief_markdown

        # persist state / audit trail
        im_tag = (f"inflow_model={inflow_model['model']}(LOO_R2={inflow_model['loo_r2']:.2f})"
                  if inflow_model else "inflow_model=none")
        self._remember(
            f"Q='{question}' | planner={the_plan['planner']} | delay={the_plan['delay_years']}y "
            f"| budget=${budget}M | vintage={params['meta']['data_vintage']} | {im_tag} "
            f"| brief={brief['md']}")

        return {
            "plan": the_plan,
            "intent": intent,
            "direct_answer": direct,
            "decision": decision,
            "recommended_chart": recommended_chart,
            "sweep": sweep,
            "runs": {k: {kk: vv for kk, vv in v.items()
                         if kk not in ("det", "bands", "mc_final")} for k, v in runs.items()},
            "comparison": comparison,
            "drivers": drivers,
            "inflow_model": inflow_model,
            "artifacts": {k: v for k, v in brief.items() if k != "brief_markdown"},
            "brief_markdown": brief_markdown,
            "brief_author": brief_author,
            "planner": the_plan["planner"],
            "trajectory": self.trajectory,
        }
