"""Capability declarations — the single place a new analysis is described.

Each `register(...)` call adds one capability. Call ORDER is classification
priority (matches the old top-to-bottom order of planner.classify_intent).
Triggers, tiers, charts, catalog text, and the Gemma few-shot example all live
here; planner / orchestrator / viz / tools derive their structures from this.
"""
import re

from agent import handlers
from agent.capabilities.registry import Capability, register

_DEF = "%(default)s"   # filled with the default budget when the prompt is built


# Budget-count helper for the compare_budgets predicate (kept local to avoid an
# import cycle with planner, which imports this registry).
_BUDGET_RE = re.compile(r"\$?\s*(\d+(?:\.\d+)?)\s*(?:m\b|million)", re.I)


def _n_budgets(q):
    return len(_BUDGET_RE.findall(q))


def _is_compare_budgets(q):
    # Mirrors planner.classify_intent lines: two+ budgets, OR a compare/vs cue
    # together with budget context.
    if _n_budgets(q) >= 2 or re.search(r"\b(compare|versus|vs\.?|or \$?\d)", q):
        if _n_budgets(q) >= 2 or "budget" in q or "$" in q or "million" in q:
            return True
    return False


# --- retrieval-tool routing (kind=retrieval; no engine, cited offline answers) ---
# A definitional/'why' question about a homelessness concept ("what is rapid
# re-housing?"). Tight on purpose: requires a definition lead-in AND a known
# concept term, and bails on any comparison/budget cue so it never steals an
# analytic question (e.g. "should we fund prevention OR supportive housing?").
_CONCEPT_TERMS = re.compile(
    r"\b(rapid re-?\s?housing|rrh|permanent supportive housing|supportive housing|psh|"
    r"prevention|point[- ]in[- ]time|pit count|continuum of care|chronic(ally)? homeless(ness)?)\b", re.I)
_DEF_LEAD = re.compile(r"\b(what (is|are|do|does)|what's|define|explain|meaning of)\b", re.I)
_CONCEPT_EXCLUDE = re.compile(
    r"\b(or|vs\.?|versus|compare|best|better|fund|spend|allocate|mix|budget|\$|cost of|"
    r"how much|how many|save|saving|roi|return|worth)\b", re.I)


def _is_concept_qa(q):
    if _CONCEPT_EXCLUDE.search(q):
        return False
    if re.search(r"\bwhy (does|is)\b.*\b(housing|home value|rent|affordab)", q):
        return True
    return bool(_DEF_LEAD.search(q) and _CONCEPT_TERMS.search(q))


# A question about the DATA itself (provenance / vintage / methodology), not a
# calculation: "what data is this based on?", "how recent is the PIT count?".
_DATA_LOOKUP = re.compile(
    r"\b(what data|which data|data source|data vintage|how (recent|old|current|fresh)|"
    r"what year|vintage|methodology|based on what|what.{0,12}based on|\bbased on\b|"
    r"where (do|does|are).{0,20}(data|numbers|figures))\b", re.I)


def _is_data_lookup(q):
    return bool(_DATA_LOOKUP.search(q))


# --- registered in classification-priority order ---------------------------
register(Capability(
    intent="greeting", runs_engine=False,
    summary="greeting — small-talk or a meta 'what can you do?' question.",
    when_to_use="small-talk (hi/hello/thanks) OR a meta question about what the tool does "
                "(what can you do, who are you, help)",
    triggers=(
        re.compile(r"^\s*(hi|hey+|hello|yo|hiya|howdy|greetings|sup|good (morning|afternoon|evening)|"
                   r"thanks|thank you|thx|help)\b", re.I),
        re.compile(r"\b(what can (you|i) (do|ask|answer)|what do you do|how do (you|i) (work|use)|"
                   r"who are you|what are you|can you help)\b", re.I),
        # "what is this" only as a meta question about the tool itself (anchored at the
        # end) — NOT "what is this city's plan?" (a noun after "this" makes it specific).
        re.compile(r"\bwhat is this( tool| app| site| thing| for)?\s*[?.!]*\s*$", re.I),
    ),
    plan_example='Q: "Hi, what can you do?" -> {"intent":"greeting","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="cost_per_person", params=("budget_musd",), handler=handlers.cost_per_person,
    chart="people_helped",
    summary="cost_per_person — people kept out of homelessness by acting now, and avoided cost per person.",
    when_to_use="cost per person helped / how many people acting now helps",
    triggers=(
        re.compile(r"\b((cost|price|spend|\$) ?(per|/) ?(person|capita)|per[- ](person|capita) "
                   r"(cost|spend)|people (we|it|you|i)? ?(would |could |can )?(help|house|keep)|"
                   r"people (helped|housed|kept)|how many people .*(help|hous|keep))", re.I),
    ),
    in_catalog=True, catalog_tier=1, catalog_order=9,
    catalog_desc="People kept out of homelessness by acting now, and avoided public cost per person.",
    plan_example='Q: "How many people would acting now help?" -> {"intent":"cost_per_person","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="out_of_scope", runs_engine=False,
    summary="out_of_scope — individual-level or sub-CoC questions the tool cannot answer.",
    when_to_use="anything about specific individuals or sub-city geographies (cannot answer)",
    triggers=(
        re.compile(r"\b(who specifically|which person|which famil(y|ies)|which household|by name|"
                   r"name the|individual|per[- ]person|household name|neighborhood|neighbourhood|"
                   r"zip ?code|street|address)", re.I),
    ),
    # Contrastive few-shot: an individual-level question wins even when it mentions a
    # "plan" or "situation" — profiling is declined regardless of the other keyword.
    plan_example=('Q: "Which family will become homeless?" -> {"intent":"out_of_scope","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}\n'
                  'Q: "What\'s the situation on my street, by address?" -> {"intent":"out_of_scope","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}'),
))

register(Capability(
    intent="data_lookup", runs_engine=False,
    summary="data_lookup — what data the model is built on (provenance, vintage, methodology).",
    when_to_use="a question about the underlying DATA — its source, vintage, recency, or methodology "
                "(not a calculation)",
    triggers=(_is_data_lookup,),
    plan_example='Q: "How recent is the PIT count?" -> {"intent":"data_lookup","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="concept_qa", runs_engine=False,
    summary="concept_qa — define a homelessness concept (rapid re-housing, PSH, PIT, chronic, etc.).",
    when_to_use="a definitional or 'why' question about a homelessness concept or term "
                "(grounded, cited context — not the cost model)",
    triggers=(_is_concept_qa,),
    plan_example='Q: "What is rapid re-housing?" -> {"intent":"concept_qa","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="equity", params=("coc",), handler=handlers.equity, chart="equity_disparity",
    summary="equity — population-level racial/demographic disparities (never profiles individuals).",
    when_to_use="population-level racial/demographic disparities in who is homeless",
    triggers=(
        re.compile(r"\b(equit|disparit|racial|by race|race|ethnic|disproportion|who bears|"
                   r"who is most affected|demographic|fair share|over-?represent)", re.I),
    ),
    in_catalog=True, catalog_tier=0, catalog_order=13,
    catalog_desc="Population-level racial/demographic disparities (who bears homelessness, who is "
                 "most unsheltered) — never profiles individuals.",
))

register(Capability(
    intent="regional", params=("budget_musd", "delay_years"), handler=handlers.regional,
    chart="regional_waiting",
    summary="regional — rank the cost of waiting across multiple cities.",
    when_to_use="rank or compare the cost of inaction across MULTIPLE cities",
    triggers=(
        re.compile(r"\b(which cit(y|ies)|across (the )?(cities|region)|regional|rank.*cit|"
                   r"every city|all (the )?(cities|cocs)|compare cities|cities (pay|cost|rank)|"
                   r"where is (it )?(worst|costliest|most expensive))", re.I),
    ),
    in_catalog=True, catalog_tier=1, catalog_order=10,
    catalog_desc="Rank the cost of waiting across multiple cities (same engine, real per-city data).",
    plan_example='Q: "Which cities pay the most for waiting?" -> {"intent":"regional","delay_years":5,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="break_even", params=("budget_musd",), handler=handlers.break_even, chart="break_even_curve",
    summary="break_even — how long the city can wait before delaying stops paying off.",
    when_to_use="how long can we wait before delaying stops paying off",
    triggers=(
        re.compile(r"\b(break[- ]?even|how long.{0,25}wait|when does .* (stop|cost)|"
                   r"how many years can|latest we can|how long before)", re.I),
    ),
    in_catalog=True, catalog_tier=1, catalog_order=2,
    catalog_desc="How long the city can wait before delaying stops paying off.",
    plan_example='Q: "How long can we afford to wait?" -> {"intent":"break_even","delay_years":5,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="compare_mix", params=("budget_musd",), handler=handlers.compare_mix, chart="mix_comparison",
    summary="compare_mix — compare prevention / rapid-rehousing / supportive-housing mixes.",
    when_to_use="prevention vs rapid-rehousing vs supportive housing",
    triggers=(
        re.compile(r"\b(prevention|rapid re-?housing|supportive housing|psh|intervention mix|"
                   r"between interventions|spend (it )?on|which program|what mix|"
                   r"(allocate|split|divide) (it )?between|split between)", re.I),
    ),
    in_catalog=True, catalog_tier=1, catalog_order=6,
    catalog_desc="Compare prevention / rapid-rehousing / supportive-housing spending mixes.",
    plan_example='Q: "Should we fund prevention or supportive housing?" -> {"intent":"compare_mix","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="compare_budgets", params=("budgets",), handler=handlers.compare_budgets,
    chart="budget_comparison",
    summary="compare_budgets — compare two or more annual budgets by 10-year cost and savings.",
    when_to_use="compare budget amounts (fill budgets[])",
    triggers=(_is_compare_budgets,),
    in_catalog=True, catalog_tier=1, catalog_order=5,
    catalog_desc="Compare two or more annual budgets by 10-year cost and savings.",
    plan_example='Q: "Is $15M or $50M better?" -> {"intent":"compare_budgets","delay_years":0,"budget_musd":15,"budgets":[15,50]}',
))

register(Capability(
    intent="roi", params=("budget_musd",), handler=handlers.roi, chart="roi",
    summary="roi — return on investment / benefit-cost ratio of acting now.",
    when_to_use="return on investment / benefit-cost ratio of acting now",
    triggers=(
        re.compile(r"\b(return on investment|roi|benefit.?cost|cost.?benefit|bang for|"
                   r"worth the (money|cost|investment|spend|budget)|pays? (it )?(back|off)|"
                   r"payback|cost.?effective|money back|(return|gain) per (dollar|\$)|"
                   r"per (dollar|\$) (spent|invested)|get (our|the|my) money back)\b", re.I),
    ),
    in_catalog=True, catalog_tier=1, catalog_order=8,
    catalog_desc="Return on investment / benefit-cost ratio of acting now (avoided cost per $ spent).",
    # Contrastive few-shot: "ROI of the plan" is ROI, not care_plan — teach the boundary.
    plan_example=('Q: "What is the ROI on a $15M program?" -> {"intent":"roi","delay_years":0,"budget_musd":15,"budgets":null}\n'
                  'Q: "What\'s the ROI of the city\'s plan?" -> {"intent":"roi","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}'),
))

register(Capability(
    intent="savings_now", params=("budget_musd",), handler=handlers.savings_now, chart="scenario_costs",
    summary="savings_now — how much acting now saves (or costs) vs doing nothing.",
    when_to_use="savings of acting now vs nothing",
    triggers=(
        re.compile(r"\b(save|saving|savings|worth (it )?(to )?act|benefit of acting)", re.I),
    ),
    in_catalog=True, catalog_tier=1, catalog_order=3,
    catalog_desc="How much acting now saves (or costs) vs doing nothing.",
))

register(Capability(
    intent="outcome_at_horizon", params=(), handler=handlers.outcome_at_horizon,
    chart="people_helped",
    summary="outcome_at_horizon — projected people homeless at the 10-year horizon.",
    when_to_use="how many homeless later",
    triggers=(
        re.compile(r"\b(how many|number of people|population|end up|will be homeless|"
                   r"homeless (count|in \d))", re.I),
    ),
    in_catalog=True, catalog_tier=1, catalog_order=4,
    catalog_desc="Projected number of people homeless at the 10-year horizon.",
))

register(Capability(
    intent="uncertainty", params=(), handler=handlers.uncertainty, chart="sensitivity_tornado",
    summary="uncertainty — how confident the headline is (range, weakest assumption, backtest error).",
    when_to_use="how confident/reliable the number is, or explain a figure's range",
    triggers=(
        re.compile(r"\b(how (confident|sure|certain|reliable|solid|robust)|"
                   r"how (wide|big|large) (is|are) the (range|band)|margin of error|"
                   r"explain (this|the|that) (number|figure|estimate)|can (we|i) (trust|rely)|"
                   r"how (good|much can we trust))", re.I),
    ),
    in_catalog=True, catalog_tier=0, catalog_order=11,
    catalog_desc="How confident the headline is: the range, the weakest assumption, the backtest error.",
    plan_example='Q: "How confident are you in that number?" -> {"intent":"uncertainty","delay_years":5,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="sensitivity", params=(), handler=handlers.sensitivity, chart="sensitivity_tornado",
    summary="sensitivity — which assumption the result is most sensitive to (what to tighten first).",
    when_to_use="which assumption matters most",
    triggers=(
        re.compile(r"\b(assumption|uncertain|least sure|confidence|most sensitive|"
                   r"matters most|what drives|driver|tighten)", re.I),
    ),
    in_catalog=True, catalog_tier=0, catalog_order=7,
    catalog_desc="Which assumption the result is most sensitive to (what to tighten first).",
))

# --- City Brief agent intents (the THIRD agent) ----------------------------
# Qualitative/contextual, NOT the cost simulator: these route to
# agent.city_brief.CityBriefAgent (the orchestrator delegates). runs_engine=False
# so the simulation pipeline is skipped — a brief is grounded retrieval + narration.
# Registered AFTER the precise analytic intents (cost_per_person..sensitivity) and
# BEFORE city_context: specific-before-general. So "what's the ROI of the city's
# plan?" routes to `roi` (precise) while "what is the city's plan?" routes to
# `care_plan` (the broad brief trigger), and "tell me about Seattle" -> city_situation.
register(Capability(
    intent="care_plan", params=("coc",), runs_engine=False, chart="city_benchmark",
    summary="care_plan — the city's strategy / care plan / what it's doing about homelessness.",
    when_to_use="the city's strategy, care plan, response, or what they are doing about homelessness "
                "(grounded context, not the cost model)",
    triggers=(
        # Broad on purpose: the precise analytic intents (roi, compare_*, etc.) are
        # registered BEFORE this, so "ROI of the plan" already routed to roi. Anything
        # mentioning a plan/strategy that ISN'T a precise analytic ask lands here.
        re.compile(r"\b(plans?\b|strateg|what (are|is) (they|the city|it) (doing|planning)|"
                   r"doing about|response to|respond(ing)? to|approach to|initiative|"
                   r"what.{0,4}s being done)", re.I),
    ),
    plan_example='Q: "What is San Diego\'s plan?" -> {"intent":"care_plan","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="city_situation", params=("coc",), runs_engine=False, chart="city_benchmark",
    summary="city_situation — a richer grounded narrative brief of a city's homelessness situation.",
    when_to_use="a richer grounded narrative brief of a city's homelessness situation "
                "(grounded context with citations, not the cost model)",
    triggers=(
        re.compile(r"\b(situation|what.{0,4}s happening|how bad|tell me about|overview|"
                   r"what.{0,4}s it like|going on|brief me)", re.I),
    ),
    plan_example='Q: "What\'s the homelessness situation in Seattle?" -> {"intent":"city_situation","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))

register(Capability(
    intent="city_context", params=("coc",), handler=handlers.city_context, chart="city_benchmark",
    summary="city_context — plain numeric profile of a city's homelessness/housing indicators.",
    when_to_use="plain numeric profile of a city's homelessness/housing indicators (snapshot)",
    triggers=(
        re.compile(r"\b(context|profile|snapshot|housing situation|how expensive|"
                   r"cost of living|indicators|benchmark)", re.I),
    ),
    in_catalog=True, catalog_tier=0, catalog_order=12,
    catalog_desc="Plain-language numeric profile of a city's homelessness + housing indicators.",
))

# Default headline + final fallback target (no trigger; reached when an in-scope
# question matches none of the above — see planner._DOMAIN_RE gate).
register(Capability(
    intent="cost_of_waiting", params=("delay_years", "budget_musd"),
    handler=handlers.cost_of_waiting, chart="cost_of_waiting",
    summary="cost_of_waiting — extra 10-year public cost of waiting N years, with a range.",
    when_to_use="extra cost of waiting",
    triggers=(),
    in_catalog=True, catalog_tier=1, catalog_order=1,
    catalog_desc="Extra 10-year public cost of waiting N years before acting, with a range.",
    # Contrastive few-shot: "tell me about the cost of waiting" is the ANALYSIS, not a
    # city_situation brief — the phrase "tell me about" alone must not pull it to a brief.
    plan_example=('Q: "What if we wait 3 years on a $15M program?" -> {"intent":"cost_of_waiting","delay_years":3,"budget_musd":15,"budgets":null}\n'
                  'Q: "Tell me about the cost of waiting." -> {"intent":"cost_of_waiting","delay_years":5,"budget_musd":' + _DEF + ',"budgets":null}'),
))

register(Capability(
    intent="clarify", runs_engine=False,
    summary="clarify — an in-scope question the supported analyses don't cover (ask the user to pick).",
    when_to_use="an in-scope homelessness/budget question the analyses above don't cover "
                "(ask the user to pick a supported analysis)",
    triggers=(),
    plan_example='Q: "What is the capital of France?" -> {"intent":"clarify","delay_years":0,"budget_musd":' + _DEF + ',"budgets":null}',
))
