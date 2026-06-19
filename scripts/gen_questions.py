"""Generate QUESTIONS.md — the reference of everything you can ask WaitCost.

Derived from the SAME sources the app routes on, so it can never drift:
  * agent/capabilities (the registry) — each capability's description + chart + kind
  * eval/routing_cases.CASES          — real example phrasings per intent

Run:  python scripts/gen_questions.py   ->  writes QUESTIONS.md at the repo root.
Adding a capability + a routing case makes it appear here automatically.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from agent import capabilities as caps          # noqa: E402
from eval.routing_cases import CASES             # noqa: E402

# Reader-friendly grouping (order = how the file reads). Internal `clarify` is
# omitted; `out_of_scope` gets its own boundary section below.
CATEGORIES = [
    ("Cost & timing", "The core: what delay costs, when it stops paying off, what acting now buys.",
     ["cost_of_waiting", "break_even", "savings_now", "outcome_at_horizon", "cost_per_person", "roi"]),
    ("Comparisons", "Put options side by side.",
     ["compare_budgets", "compare_mix", "regional"]),
    ("Confidence & drivers", "How much to trust the number, and what moves it.",
     ["uncertainty", "sensitivity"]),
    ("Equity", "Who bears homelessness — population level only.",
     ["equity"]),
    ("City context & definitions", "Background, not a calculation — grounded in cited sources.",
     ["city_situation", "care_plan", "city_context", "concept_qa", "data_lookup"]),
    ("Getting started", "Say hello or ask what it can do.",
     ["greeting"]),
]

RETRIEVAL = {"concept_qa", "data_lookup"}
CITY_BRIEF = {"care_plan", "city_situation"}
_SMALL = {"of", "at", "vs", "per", "the", "a", "to", "by", "on", "in", "and"}
# Display-name overrides for ids that don't title-case nicely (acronyms, etc.).
# Presentation only — anything not listed falls back to title-case, so new tools
# still appear automatically.
_LABELS = {
    "roi": "ROI", "concept_qa": "Concept Q&A", "data_lookup": "Data & sources",
    "break_even": "Break-even", "city_context": "City snapshot",
    "outcome_at_horizon": "People homeless at the horizon", "regional": "Across cities",
}


def label(intent):
    """A clean title for an intent id (e.g. cost_of_waiting -> 'Cost of waiting')."""
    if intent in _LABELS:
        return _LABELS[intent]
    words = intent.split("_")
    return " ".join(w if (i and w in _SMALL) else w.capitalize()
                    for i, w in enumerate(words))


def examples_for(intent, limit=5):
    """Clean example phrasings from the routing benchmark (skip ambiguous
    'collision' cases), order-preserving + deduped."""
    seen, out = set(), []
    for q, exp, kind in CASES:
        if exp == intent and kind in ("clear", "paraphrase") and q not in seen:
            seen.add(q)
            out.append(q)
        if len(out) >= limit:
            break
    return out


def returns_line(cap):
    if cap.intent in RETRIEVAL:
        return "a plain-English, **cited** answer — no simulation."
    if cap.intent in CITY_BRIEF:
        return "a grounded, **cited** city narrative (general context, not the cost model)."
    if cap.intent == "greeting":
        return "a short orientation to what you can ask."
    if cap.runs_engine:
        base = "a quantified estimate with an **80% range**"
        return base + (f", plus the **{cap.chart}** chart." if cap.chart else ".")
    return "a guided response."


def render():
    L = []
    L.append("# What you can ask WaitCost")
    L.append("")
    L.append("> Auto-generated from the app's capability registry "
             "(`python scripts/gen_questions.py`). Every type below is something "
             "the app actually routes and answers.")
    L.append("")
    L.append("**Two things to know first:**")
    L.append("")
    L.append("- Questions apply to the **city you've selected** (Los Angeles / CA-600 by "
             "default — switch cities in the app header). Some types let you name a city in the question.")
    L.append("- Every dollar figure is a **range, not a point** — the model reports the 80% range "
             "and is explicit about what's calibrated vs. assumed.")
    L.append("")

    for title, blurb, intents in CATEGORIES:
        L.append(f"## {title}")
        L.append("")
        L.append(f"_{blurb}_")
        L.append("")
        for intent in intents:
            cap = caps.by_intent(intent)
            if not cap:
                continue
            desc = (cap.catalog_desc or cap.when_to_use or "").strip().rstrip(".")
            L.append(f"### {label(intent)}")
            if desc:
                L.append(f"{desc[0].upper() + desc[1:]}.")
            L.append("")
            for q in examples_for(intent):
                L.append(f"- “{q}”")
            L.append("")
            L.append(f"**You get:** {returns_line(cap)}")
            L.append("")

    # Authored: the compound / multi-budget tricks (not single intents).
    L.append("## Power moves — compound questions")
    L.append("")
    L.append("WaitCost answers a question as one *or more* tool calls, so you can pack several "
             "asks into one sentence:")
    L.append("")
    L.append("- **Several budgets at once** — “What does it cost to wait 3 years on a **$15M and "
             "a $25M** program?” returns the cost of waiting for *each* budget, side by side, with a "
             "per-budget chart.")
    L.append("- **“…and…” means “answer each”**; **“which is better?” / “vs”** means "
             "“compare the totals” (e.g. “Is $15M **or** $50M better?”).")
    L.append("- Every value you mention is answered — the app never silently drops one. If it can't "
             "cover something, it says so.")
    L.append("")

    # Authored: the boundary, from the out_of_scope capability + its examples.
    oos = caps.by_intent("out_of_scope")
    L.append("## What WaitCost won't answer")
    L.append("")
    L.append("By design, it answers at the **city (CoC) level** and **never about individuals**. "
             "These are politely declined:")
    L.append("")
    for q in examples_for("out_of_scope"):
        L.append(f"- “{q}”")
    L.append("")
    L.append("It also declines when the data can't support a credible answer (e.g. a city with too "
             "thin a count), rather than showing an unsupported number.")
    L.append("")
    return "\n".join(L).rstrip() + "\n"


def main():
    out_path = os.path.join(_REPO, "QUESTIONS.md")
    with open(out_path, "w") as f:
        f.write(render())
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
