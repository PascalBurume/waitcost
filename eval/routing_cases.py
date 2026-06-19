"""Routing benchmark — a judge-style labeled set of questions → expected intent.

The point: prove the agent routes *all kinds* of questions, not just the clean
demo phrasings. Each case is tagged:

  clear      — a natural, unambiguous phrasing the deterministic rules MUST ace.
  paraphrase — a reworded / colloquial variant the rules should still get.
  collision  — deliberately ambiguous or adversarial (a word that belongs to two
               intents, e.g. "the ROI of the city's plan"). These are where the
               offline LLM router earns its keep; the rule baseline is allowed to
               miss some, and the benchmark reports them separately.

Used by eval/test_routing_benchmark.py (rule mode, deterministic) and runnable
live against Gemma to show the LLM beats the regex on the collision tier.
"""

# (question, expected_intent, kind)
CASES = [
    # --- greeting -----------------------------------------------------------
    ("hi", "greeting", "clear"),
    ("hello there", "greeting", "clear"),
    ("good evening", "greeting", "clear"),
    ("thanks!", "greeting", "clear"),
    ("what can you do?", "greeting", "clear"),
    ("who are you?", "greeting", "clear"),
    ("help", "greeting", "clear"),
    ("how do I use this?", "greeting", "paraphrase"),
    ("what is this?", "greeting", "clear"),
    ("what is this tool?", "greeting", "paraphrase"),
    # adversarial: "what is this <noun>" must NOT be read as the meta greeting
    ("What is this city's plan?", "care_plan", "collision"),
    ("What is this city's situation?", "city_situation", "collision"),

    # --- cost_per_person ----------------------------------------------------
    ("How many people would acting now help?", "cost_per_person", "clear"),
    ("What is the cost per person helped?", "cost_per_person", "clear"),
    ("How many people can we keep off the street?", "cost_per_person", "paraphrase"),
    ("How many people housed per dollar?", "cost_per_person", "paraphrase"),
    ("What's the avoided cost per capita?", "cost_per_person", "paraphrase"),

    # --- out_of_scope (safety-critical: individual / sub-CoC) ---------------
    ("Which family on 5th street will become homeless?", "out_of_scope", "clear"),
    ("Name the person who will lose their housing.", "out_of_scope", "clear"),
    ("Which individual is most at risk?", "out_of_scope", "clear"),
    ("What about the household at 12 Elm Street?", "out_of_scope", "clear"),
    ("Homelessness in zip code 90001?", "out_of_scope", "clear"),
    ("Which neighborhood is worst?", "out_of_scope", "paraphrase"),
    ("Tell me which family's plan is failing.", "out_of_scope", "collision"),
    ("What's the situation on my street, by address?", "out_of_scope", "collision"),

    # --- equity -------------------------------------------------------------
    ("What are the racial disparities in homelessness?", "equity", "clear"),
    ("Who bears homelessness most by race?", "equity", "clear"),
    ("Is there demographic over-representation?", "equity", "clear"),
    ("Which racial group is most unsheltered?", "equity", "paraphrase"),
    ("Show me equity by ethnicity.", "equity", "paraphrase"),
    ("Who is most affected, by race?", "equity", "paraphrase"),

    # --- regional -----------------------------------------------------------
    ("Which cities pay the most for waiting?", "regional", "clear"),
    ("Rank the cities by cost of inaction.", "regional", "clear"),
    ("Compare the cost of waiting across all CoCs.", "regional", "clear"),
    ("Where is it worst across the region?", "regional", "paraphrase"),
    ("Which city is the costliest to delay in?", "regional", "paraphrase"),

    # --- care_plan (CityBriefAgent) -----------------------------------------
    ("What is San Diego's plan?", "care_plan", "clear"),
    ("What is the city's strategy?", "care_plan", "clear"),
    ("What are they doing about homelessness?", "care_plan", "clear"),
    ("How is the city responding to homelessness?", "care_plan", "clear"),
    ("What initiatives are in place?", "care_plan", "clear"),
    ("Describe the care plan.", "care_plan", "clear"),
    ("What's their approach to ending homelessness?", "care_plan", "paraphrase"),
    ("Who leads the response here and what's the strategy?", "care_plan", "paraphrase"),
    ("What's the action plan for homelessness?", "care_plan", "paraphrase"),

    # --- city_situation (CityBriefAgent) ------------------------------------
    ("What's the homelessness situation in Seattle?", "city_situation", "clear"),
    ("Tell me about Seattle.", "city_situation", "clear"),
    ("Give me an overview of homelessness here.", "city_situation", "clear"),
    ("How bad is homelessness in this city?", "city_situation", "clear"),
    ("What's happening with homelessness here?", "city_situation", "clear"),
    ("What's it like in this city?", "city_situation", "paraphrase"),
    ("Brief me on this city.", "city_situation", "paraphrase"),

    # --- city_context (numeric snapshot) ------------------------------------
    ("Show me the housing profile.", "city_context", "clear"),
    ("What are the housing indicators?", "city_context", "clear"),
    ("How expensive is housing here?", "city_context", "clear"),
    ("Give me the cost-of-living snapshot.", "city_context", "paraphrase"),
    ("City benchmark numbers, please.", "city_context", "paraphrase"),

    # --- break_even ---------------------------------------------------------
    ("How long can we wait before it stops paying off?", "break_even", "clear"),
    ("When does waiting stop being worth it?", "break_even", "clear"),
    ("What's the break-even year?", "break_even", "clear"),
    ("How many years can we afford to delay?", "break_even", "paraphrase"),
    ("What's the latest we can act and still come out ahead?", "break_even", "paraphrase"),

    # --- compare_mix --------------------------------------------------------
    ("Should we fund prevention or supportive housing?", "compare_mix", "clear"),
    ("Prevention vs rapid re-housing?", "compare_mix", "clear"),
    ("What mix of programs should we fund?", "compare_mix", "clear"),
    ("How should we split between interventions?", "compare_mix", "paraphrase"),
    ("Is PSH or prevention the better use of funds?", "compare_mix", "paraphrase"),

    # --- compare_budgets ----------------------------------------------------
    ("Is $15M or $50M the better budget?", "compare_budgets", "clear"),
    ("Compare a $10M and a $30M annual budget.", "compare_budgets", "clear"),
    ("$20M versus $40M — which wins?", "compare_budgets", "clear"),
    ("Which is better, $15M or $25M a year?", "compare_budgets", "paraphrase"),

    # --- roi ----------------------------------------------------------------
    ("What's the ROI on a $15M program?", "roi", "clear"),
    ("Is it worth the investment?", "roi", "clear"),
    ("What's the benefit-cost ratio?", "roi", "clear"),
    ("Do we get our money back?", "roi", "paraphrase"),
    ("What's the return per dollar spent?", "roi", "paraphrase"),
    ("What's the ROI of the city's plan?", "roi", "collision"),
    ("Is the city's strategy worth the money?", "roi", "collision"),

    # --- savings_now --------------------------------------------------------
    ("How much do we save by acting now?", "savings_now", "clear"),
    ("What are the savings of acting now versus nothing?", "savings_now", "clear"),
    ("What's the benefit of acting now?", "savings_now", "paraphrase"),
    ("How much money does acting today save us?", "savings_now", "paraphrase"),

    # --- outcome_at_horizon -------------------------------------------------
    ("How many people will be homeless in 2034?", "outcome_at_horizon", "clear"),
    ("What's the projected homeless count at the horizon?", "outcome_at_horizon", "clear"),
    ("How many people end up homeless if we do nothing?", "outcome_at_horizon", "paraphrase"),

    # --- uncertainty --------------------------------------------------------
    ("How confident are you in that number?", "uncertainty", "clear"),
    ("Can we trust this estimate?", "uncertainty", "clear"),
    ("How wide is the range?", "uncertainty", "clear"),
    ("What's the margin of error?", "uncertainty", "paraphrase"),
    ("Explain how reliable that figure is.", "uncertainty", "paraphrase"),

    # --- sensitivity --------------------------------------------------------
    ("Which assumption matters most?", "sensitivity", "clear"),
    ("What drives the result?", "sensitivity", "clear"),
    ("Which assumption are we least sure about?", "sensitivity", "clear"),
    ("What should we tighten first?", "sensitivity", "paraphrase"),

    # --- cost_of_waiting (default / fallback) -------------------------------
    ("What does it cost to wait 3 years?", "cost_of_waiting", "clear"),
    ("What's the extra cost of waiting 5 years on $15M?", "cost_of_waiting", "clear"),
    ("How much more does it cost if we wait two years?", "cost_of_waiting", "clear"),
    ("What if we delay?", "cost_of_waiting", "paraphrase"),
    ("Tell me about the cost of waiting.", "cost_of_waiting", "collision"),

    # --- concept_qa (definitional / 'why', cited retrieval) -----------------
    ("What is rapid re-housing?", "concept_qa", "clear"),
    ("What is permanent supportive housing?", "concept_qa", "clear"),
    ("What does chronic homelessness mean?", "concept_qa", "clear"),
    ("Why does housing cost drive homelessness?", "concept_qa", "paraphrase"),

    # --- data_lookup (provenance / vintage / methodology) -------------------
    ("What data is this based on?", "data_lookup", "clear"),
    ("How recent is the PIT count?", "data_lookup", "clear"),
    ("What's the data vintage?", "data_lookup", "paraphrase"),

    # --- clarify (in-scope-but-unmapped / off-topic) ------------------------
    ("What is the capital of France?", "clarify", "clear"),
    ("Tell me a joke.", "clarify", "paraphrase"),
]
