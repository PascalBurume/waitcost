"""Chart-coverage sweep — run every benchmark question through the FULL routing +
visualization path and prove each one yields a valid, render-ready graphic.

This answers "ask a hundred questions and see how the graphics appear": for each
question we classify the intent (the analyst agent), recommend a chart (the viz
agent), build the spec from real engine output, and validate it is non-empty and
JSON-serializable. Distinct charts are built once (cached) so the sweep is fast.

    WAITCOST_PLANNER=rule .venv/bin/python eval/chart_coverage.py
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.routing_cases import CASES
from agent import planner
from analysis.viz import VizAgent

# Intents that intentionally render NO chart (declines / meta) — the UI shows a
# card, not a graphic. Everything else must produce a buildable spec.
_NO_CHART = {"greeting", "clarify", "out_of_scope"}


def sweep(coc="CA-600", n_mc=20):
    va = VizAgent()
    cache = {}                       # chart_name -> built spec (build once)
    rows = []                        # (question, intent, chart, ok, err)
    intent_counts = collections.Counter()
    chart_counts = collections.Counter()
    for q, _expected, _kind in CASES:
        intent = planner.classify_intent(q)
        intent_counts[intent] += 1
        if intent in _NO_CHART:
            rows.append((q, intent, None, True, None))
            continue
        chart = va.recommend(intent)
        chart_counts[chart] += 1
        if chart not in cache:
            try:
                spec = va.build(chart, coc=coc, n_mc=n_mc)
                json.dumps(spec)                          # must serialize for the API/UI
                assert spec.get("series"), "empty series"
                cache[chart] = ("ok", spec)
            except Exception as e:                        # pragma: no cover - reported
                cache[chart] = ("err", str(e))
        status, payload = cache[chart]
        rows.append((q, intent, chart, status == "ok", None if status == "ok" else payload))
    return {"rows": rows, "intent_counts": intent_counts, "chart_counts": chart_counts,
            "built": {k: v[0] for k, v in cache.items()}}


def _report(r):
    rows = r["rows"]
    ok = sum(1 for x in rows if x[3])
    print(f"\n=== Chart coverage — {len(rows)} questions ===")
    print(f"buildable: {ok}/{len(rows)}  ({ok/len(rows):.1%})")
    print(f"\ndistinct charts built ({len(r['chart_counts'])}):")
    for chart, n in r["chart_counts"].most_common():
        print(f"  {r['built'].get(chart,'-'):4} {chart:22} ← {n} question(s)")
    print(f"\nintent distribution ({len(r['intent_counts'])} intents):")
    for intent, n in r["intent_counts"].most_common():
        print(f"  {intent:20} {n}")
    fails = [x for x in rows if not x[3]]
    if fails:
        print("\nFAILURES:")
        for q, intent, chart, _ok, err in fails:
            print(f"  {q!r} [{intent}->{chart}]: {err}")


if __name__ == "__main__":
    _report(sweep())
