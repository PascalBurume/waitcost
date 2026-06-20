"""Retrieval tools — grounded, offline answers for the questions that are NOT a
cost calculation: 'what is rapid re-housing?' (concept_qa) and 'what data is this
based on?' (data_lookup).

Same contract as the CityBriefAgent: every answer is grounded in a cited local
source, carries the "general context — not the calibrated cost model" label, and
stays fully offline (Claude may only REPHRASE the curated text, number-guarded —
it can never introduce a fact or figure). These are registered as capabilities
(kind=retrieval) so the router can route to them like any other tool.
"""
import json
import os
import re

from agent import planner

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONCEPTS_PATH = os.path.join(_REPO, "data", "concepts.json")
LABEL = "General context — not the calibrated cost model."


def _load_concepts():
    try:
        with open(_CONCEPTS_PATH) as f:
            return json.load(f)
    except Exception:
        return {"label": LABEL, "concepts": []}


def _match_concept(question):
    q = (question or "").lower()
    for c in _load_concepts().get("concepts", []):
        for term in [c["key"], *c.get("aliases", [])]:
            if term.lower() in q:
                return c
    return None


def concept_qa(question, params=None):
    """Answer a definitional / 'why' question about a homelessness concept from the
    cited knowledge file. Deterministic by default; Claude may rephrase the curated
    definition (number-guarded against it). Returns a labelled, sourced dict."""
    c = _match_concept(question)
    if not c:
        # AI-assist fallback: we recognized a concept question but have no curated
        # entry — guide the user rather than guess (fully offline, never fabricates).
        known = ", ".join(x["key"] for x in _load_concepts().get("concepts", []))
        return {
            "matched": False,
            "answer": ("I don't have a sourced definition for that yet. I can explain these "
                       f"concepts from cited sources: {known}. Or ask a cost-of-waiting, "
                       "break-even, savings, ROI, or budget/mix question to run the model."),
            "sources": [], "label": LABEL,
        }
    definition = c["definition"]
    # Optional Claude rephrase, guarded so it can only restate the curated definition.
    prompt = ("Rephrase the following definition in <=70 words of plain markdown for a city "
              "budget director. Do NOT add any fact, number, or claim not present in it.\n\n"
              f"DEFINITION:\n{definition}")
    answer = planner.narrate_grounded(prompt, definition) or definition
    return {"matched": True, "concept": c["key"], "answer": answer,
            "sources": [c["source"]], "label": LABEL}


def data_lookup(question, params):
    """Answer a 'what data / how recent / what's this based on' question from the
    calibration provenance (config/params.yaml meta + data/SOURCES.md). Deterministic
    and cited — the figures come only from the params block, never invented."""
    meta = params.get("meta", {}) if params else {}
    vintage = meta.get("data_vintage", "see data/SOURCES.md")
    coc = meta.get("coc", "the calibrated CoC")
    mc = meta.get("monte_carlo_runs")
    horizon = meta.get("horizon_months")
    disc = meta.get("discount_annual")
    parts = [f"**This analysis is calibrated for {coc}.**",
             f"**Data vintage:** {vintage}."]
    bits = []
    if horizon:
        bits.append(f"a {int(horizon)//12}-year horizon")
    if disc is not None:
        bits.append(f"a {float(disc)*100:.0f}% social discount rate")
    if mc:
        bits.append(f"{int(mc)} Monte-Carlo runs per scenario")
    if bits:
        parts.append("Model settings: " + ", ".join(bits) + ".")
    parts.append("Homeless counts are real HUD 2024 Point-in-Time data; economic signals are "
                 "Census ACS 2024 1-year estimates (reproducible from the Census API). Key flow "
                 "rates are calibrated from HUD System Performance Measures (FY2023); the rest are "
                 "documented priors. Full provenance is in data/SOURCES.md.")
    sources = [
        {"title": "HUD 2024 PIT (CoC Populations & Subpopulations)",
         "url": "https://www.hudexchange.info/programs/hdx/pit-hic/"},
        {"title": "U.S. Census ACS 2024 1-year estimates", "url": "https://www.census.gov/programs-surveys/acs"},
        {"title": "WaitCost data sources (data/SOURCES.md)", "url": "data/SOURCES.md"},
    ]
    return {"matched": True, "answer": " ".join(parts), "sources": sources, "label": LABEL}
