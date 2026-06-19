"""CityBriefAgent — the third agent: grounded city homelessness briefings.

The two existing agents are quantitative: the analyst orchestrator runs the
calibrated cost simulator, and the viz agent picks charts. This third agent
answers the *contextual* questions a judge or director actually asks first —
"What's the homelessness situation in Seattle?", "What is San Diego's plan?" —
and it does so WITHOUT touching the cost model's maths.

Every answer is grounded:
  * numbers come ONLY from the engine (`skills.retrieve_us_context`) — never invented;
  * narrative + strategy come ONLY from the curated registry (`data/city_sources.json`),
    each with a real citation;
  * an optional equity headline is woven in (already population-level + labelled).

It keeps the same conventions as WaitCostAgent: a `trajectory` of
`{skill, tier, approved}` steps (all Tier 0, read-only), a MEMORY.md audit line,
and a hard "general context — not the calibrated cost model" label so the brief is
never confused with the simulator. Offline by default; an opt-in `WAITCOST_ONLINE=1`
flag may refresh a brief from the plan URL but never becomes a hard dependency.
"""
import datetime
import json
import os
from pathlib import Path

from agent import skills, planner, web_search

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_REGISTRY = os.path.join(_REPO, "data", "city_sources.json")

LABEL = "General context — not the calibrated cost model."

# All retrieval here is Tier 0 (read-only). Mirrors orchestrator.SKILL_PRESENTATION
# so a streamed brief reads like a reasoning timeline, not raw function names.
_PRESENTATION = {
    "load_city_sources": ("Loading city source registry", "Curated lead agency + care plan + citations"),
    "retrieve_us_context": ("Retrieving city context", "HUD PIT + Census ACS indicators"),
    "equity_analysis": ("Equity analysis", "Population-level racial disparities (no profiling)"),
    "fetch_live_plan": ("Refreshing from plan URL", "Live web (opt-in WAITCOST_ONLINE)"),
}


class CityBriefAgent:
    def __init__(self, registry_path=_DEFAULT_REGISTRY, memory_path="MEMORY.md", on_step=None):
        self.registry_path = Path(registry_path)
        self.memory_path = Path(memory_path)
        self._on_step = on_step
        self.trajectory = []
        self._registry = self._load_registry()
        self._by_coc = {c.get("coc"): c for c in self._registry.get("cities", [])}

    # --- registry + small helpers (mirror WaitCostAgent shapes) --------------
    def _load_registry(self):
        try:
            with open(self.registry_path) as f:
                return json.load(f)
        except Exception:
            return {"national_frameworks": [], "cities": []}

    def _step(self, skill):
        """Record a Tier-0 step (read-only) and stream it, like _check_tier does."""
        step = {"skill": skill, "tier": 0, "approved": False}
        self.trajectory.append(step)
        if self._on_step is not None:
            label, detail = _PRESENTATION.get(skill, (skill, ""))
            try:
                self._on_step({**step, "label": label, "detail": detail, "status": "running"})
            except Exception:
                pass

    def _remember(self, text):
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            with open(self.memory_path, "a") as f:
                f.write(f"\n- [{stamp}] {text}")
        except Exception:
            pass

    # --- the national framing the local plans align to -----------------------
    def _national_context(self):
        fw = self._registry.get("national_frameworks", [])
        allin = next((f for f in fw if "All In" in f.get("title", "")), None)
        if not allin:
            return ("Local plans align to the federal framework for preventing and ending "
                    "homelessness (USICH) and HUD's Continuum of Care program.")
        return (f"Aligns to **{allin['title']}** — {allin.get('note', '').strip()}").rstrip(" .") + "."

    # --- the public method ---------------------------------------------------
    def brief(self, coc, question=None):
        """Return a grounded city brief (see module docstring for the contract)."""
        entry = self._by_coc.get(coc)
        self._step("load_city_sources")

        # Unknown CoC: still return a labelled, well-formed (empty-sourced) brief.
        if not entry:
            self._remember(f"CITY-BRIEF: no registry entry for {coc} | Q='{question}'")
            return {
                "coc": coc, "city": coc, "lead_agency": None,
                "plan": {"title": None, "url": None,
                         "summary": "No curated care-plan source is on file for this CoC yet."},
                "situation": f"No curated briefing source is on file for {coc} yet.",
                "indicators": {}, "national_context": self._national_context(),
                "sources": [], "label": LABEL, "online": False,
                "trajectory": list(self.trajectory),
            }

        # Indicators — the ONLY numeric source (real HUD PIT + Census ACS).
        self._step("retrieve_us_context")
        try:
            ctx = skills.retrieve_us_context(coc)
            indicators = ctx.get("indicators", {})
            city_name = ctx.get("name", entry.get("city", coc))
        except Exception:
            indicators, city_name = {}, entry.get("city", coc)

        # Equity headline (already grounded + labelled) — woven into the narrative.
        self._step("equity_analysis")
        equity_line = None
        try:
            from analysis.equity import headline
            equity_line = headline(coc)
        except Exception:
            equity_line = None

        situation_note = (entry.get("situation_note") or "").strip()
        lead_agency = entry.get("lead_agency")
        plan_title = entry.get("plan_title")
        plan_url = entry.get("plan_url")

        # Deterministic, fully-grounded prose (the always-correct fallback).
        det_situation = self._compose_situation(city_name, entry, indicators, situation_note, equity_line)
        det_plan_summary = self._compose_plan_summary(lead_agency, plan_title, situation_note)

        # Optional Gemma phrasing, number-guarded against ONLY these facts.
        allowed = self._fact_whitelist(indicators, situation_note, equity_line, plan_title)
        situation = planner.narrate_grounded(
            self._situation_prompt(city_name, entry, indicators, situation_note, equity_line),
            allowed) or det_situation
        plan_summary = planner.narrate_grounded(
            self._plan_prompt(lead_agency, plan_title, situation_note), allowed) or det_plan_summary

        # Sources actually used: the registry's key sources for this city.
        sources = [{"title": s.get("title"), "url": s.get("url")}
                   for s in entry.get("key_sources", []) if s.get("url")]
        if not sources and plan_url:
            sources = [{"title": plan_title or "Care plan", "url": plan_url}]

        # Optional live refresh — opt-in, never a hard dependency.
        online = False
        if web_search.online_enabled() and plan_url:
            self._step("fetch_live_plan")
            if web_search.fetch(plan_url) is not None:
                online = True
                if not any(s["url"] == plan_url for s in sources):
                    sources.append({"title": f"{plan_title or 'Care plan'} (live)", "url": plan_url})

        self._remember(f"CITY-BRIEF: {coc} ({city_name}) | sources={len(sources)} "
                       f"| online={online} | Q='{question}'")

        return {
            "coc": coc, "city": city_name, "lead_agency": lead_agency,
            "plan": {"title": plan_title, "url": plan_url, "summary": plan_summary},
            "situation": situation,
            "indicators": indicators,
            "national_context": self._national_context(),
            "sources": sources,
            "label": LABEL,
            "online": online,
            "trajectory": list(self.trajectory),
        }

    # --- deterministic composition (every figure traces to the facts) --------
    def _compose_situation(self, city, entry, ind, note, equity_line):
        parts = [f"**{city}** ({entry.get('coc_name', entry.get('coc'))})"]
        if ind:
            parts[0] += (f" has about **{ind['homeless_pit_total']:,} people homeless** in the latest "
                         f"point-in-time count ({ind['homeless_rate_per_1k']}/1,000 residents; "
                         f"{ind['unsheltered_share_pct']}% unsheltered, {ind['chronic_share_pct']}% chronic). "
                         f"Housing pressure is high: median home value ${ind['median_home_value_usd']:,} "
                         f"against median household income ${ind['median_household_income_usd']:,} "
                         f"(ratio {ind['home_value_to_income_ratio']}x); poverty {ind['poverty_rate_pct']}%.")
        else:
            parts[0] += "."
        if note:
            parts.append(note)
        if equity_line:
            parts.append(equity_line)
        return " ".join(parts)

    def _compose_plan_summary(self, lead_agency, plan_title, note):
        head = ""
        if lead_agency and plan_title:
            head = f"{lead_agency} leads the response under **{plan_title}**. "
        elif lead_agency:
            head = f"{lead_agency} leads the local response. "
        elif plan_title:
            head = f"**{plan_title}**. "
        return (head + note).strip() or "Care-plan details are pending verification."

    # --- Gemma prompts + the number whitelist --------------------------------
    def _fact_whitelist(self, ind, note, equity_line, plan_title):
        """The exact text whose numbers Gemma is allowed to echo (number guard)."""
        # The rate is expressed "per 1,000 residents"; whitelist that denominator so
        # the number guard treats the 1,000 scale label as grounded (it's not a figure).
        lines = ["rate scale: per 1,000 residents"]
        for k, v in (ind or {}).items():
            lines.append(f"{k}: {v}")
        if note:
            lines.append(note)
        if equity_line:
            lines.append(equity_line)
        if plan_title:
            lines.append(plan_title)
        return "\n".join(lines)

    def _situation_prompt(self, city, entry, ind, note, equity_line):
        facts = self._fact_whitelist(ind, note, equity_line, None)
        return (
            f"You are a policy analyst writing a SHORT grounded briefing (<=120 words, markdown) on "
            f"the homelessness situation in {city} ({entry.get('coc_name', '')}). Use ONLY the facts "
            "below; do NOT invent, round, or compute any new number — every figure you write must "
            "appear verbatim in FACTS. Weave the indicators and the situation note into plain prose. "
            "Do not profile individuals or neighborhoods.\n\nFACTS:\n" + facts)

    def _plan_prompt(self, lead_agency, plan_title, note):
        return (
            f"You are a policy analyst. In <=80 words of markdown, summarize the homelessness care "
            f"plan / response strategy. The lead agency is {lead_agency or 'the local CoC'} and the "
            f"plan is titled '{plan_title or 'the local plan'}'. Use ONLY the strategy description "
            "below; do NOT invent any figure, plan name, or initiative not present in it.\n\n"
            "STRATEGY:\n" + (note or ""))
