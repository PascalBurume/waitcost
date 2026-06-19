"""Score the routing benchmark (eval/routing_cases.py) against a classifier.

Run directly to see a full report (rule mode by default):
    WAITCOST_PLANNER=rule .venv/bin/python eval/routing_benchmark.py
    WAITCOST_PLANNER=gemma .venv/bin/python eval/routing_benchmark.py   # live LLM

Importable: `score(classifier)` returns a structured result the pytest gate uses.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.routing_cases import CASES


def _rule_classifier(q):
    from agent import capabilities as caps
    from agent import planner
    # caps.classify is the pure trigger walk; planner.classify_intent adds the
    # in-scope fallback (-> cost_of_waiting / clarify). We score the full path.
    return planner.classify_intent(q)


def _gemma_classifier(q):
    from agent import planner
    # Build params just for the default budget; routing only needs meta.
    params = {"meta": {"default_budget_musd": 10.0}}
    return planner._gemma_plan(q, params)["intent"]


def score(classifier=None):
    classifier = classifier or _rule_classifier
    by_kind = collections.defaultdict(lambda: [0, 0])      # kind -> [correct, total]
    confusion = []                                          # (q, expected, got, kind)
    per_intent = collections.defaultdict(lambda: [0, 0])   # intent -> [correct, total]
    for q, expected, kind in CASES:
        got = classifier(q)
        ok = (got == expected)
        by_kind[kind][1] += 1
        by_kind[kind][0] += int(ok)
        per_intent[expected][1] += 1
        per_intent[expected][0] += int(ok)
        if not ok:
            confusion.append((q, expected, got, kind))
    total = sum(v[1] for v in by_kind.values())
    correct = sum(v[0] for v in by_kind.values())
    # "must-pass" tier = clear + paraphrase (the LLM-territory collisions excluded)
    mp_correct = by_kind["clear"][0] + by_kind["paraphrase"][0]
    mp_total = by_kind["clear"][1] + by_kind["paraphrase"][1]
    return {
        "total": total, "correct": correct, "overall_acc": correct / total,
        "by_kind": {k: (c, t, c / t) for k, (c, t) in by_kind.items()},
        "must_pass_acc": mp_correct / mp_total, "must_pass_total": mp_total,
        "per_intent": {k: (c, t) for k, (c, t) in sorted(per_intent.items())},
        "confusion": confusion,
    }


def _report(label, r):
    print(f"\n=== Routing benchmark — {label} ===")
    print(f"overall: {r['correct']}/{r['total']} = {r['overall_acc']:.1%}")
    for kind in ("clear", "paraphrase", "collision"):
        if kind in r["by_kind"]:
            c, t, a = r["by_kind"][kind]
            print(f"  {kind:11} {c}/{t} = {a:.1%}")
    print(f"  must-pass (clear+paraphrase): {r['must_pass_acc']:.1%}")
    if r["confusion"]:
        print("misroutes:")
        for q, expected, got, kind in r["confusion"]:
            print(f"  [{kind}] {q!r}\n        expected {expected!r}, got {got!r}")


if __name__ == "__main__":
    mode = os.environ.get("WAITCOST_PLANNER", "rule").lower()
    clf = _gemma_classifier if mode == "gemma" else _rule_classifier
    _report(mode, score(clf))
