#!/usr/bin/env python3
"""WaitCost skill CLI — the thin, offline entry point the Agent Skill calls.

This is a deliberately tiny argparse wrapper over `api/payloads.py`, which is
already the single source of payload logic (it wraps the orchestrator → skills →
engine). Because the skill, the FastAPI app, and the agent all funnel through the
same `payloads`, they CANNOT disagree on a number — the engine owns every figure.

It is offline and deterministic: no network, no API key. When Claude (rather than
the bundled local Claude planner) drives this CLI, NL understanding is Claude's and
every computed figure is still the Python engine's.

Safety boundaries are preserved here, not just in prose:
  * Tier-2 (recommending a binding allocation) stays gated. `make_agent` defaults
    to max_auto_tier=1, so a Tier-2 step RAISES unless `--approve-allocation` is
    passed — which Claude must only do after explicit human confirmation.
  * `guard` reuses the engine's number-guard so Claude can self-check that a memo
    introduces no figure the engine didn't produce.

Usage (run from anywhere; the repo root is added to sys.path):
    python waitcost_cli.py ask "What if we wait 3 years on a $15M program?" --coc CA-600
    python waitcost_cli.py chart people_helped --coc IL-510 --budget 50 --delay 5
    python waitcost_cli.py tools
    python waitcost_cli.py cocs
    python waitcost_cli.py guard --facts facts.json --text memo.txt
"""
import argparse
import json
import os
import sys

# Resolve the repo root (…/inactioncost) from this file's location:
#   skills/waitcost/scripts/waitcost_cli.py  ->  up 3 levels
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


def _emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="waitcost", description="WaitCost offline analyst CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="Run the full agent loop on a natural-language question")
    a.add_argument("question")
    a.add_argument("--coc", default=None, help="Continuum of Care, e.g. CA-600 (default: bundled CA-600)")
    a.add_argument("--approve-allocation", action="store_true",
                   help="Authorize the Tier-2 allocation step — ONLY after explicit human approval")

    c = sub.add_parser("chart", help="Build one render-ready chart spec (JSON)")
    c.add_argument("name")
    c.add_argument("--coc", default="CA-600")
    c.add_argument("--budget", type=float, default=50.0)
    c.add_argument("--delay", type=int, default=3)

    sub.add_parser("tools", help="The capability catalog + counts")
    sub.add_parser("cocs", help="The cities the engine supports")

    g = sub.add_parser("guard", help="Number-guard a memo against the engine's facts")
    g.add_argument("--facts", required=True, help="Path to JSON of allowed facts (the engine output)")
    g.add_argument("--text", required=True, help="Path to the memo text to check")

    args = ap.parse_args(argv)
    from api import payloads as P   # imported here so --help works without the engine deps

    if args.cmd == "ask":
        _emit(P.ask_payload(args.question, approve_allocation=args.approve_allocation, coc=args.coc))
    elif args.cmd == "chart":
        _emit(P.chart_payload(args.name, coc=args.coc, budget=args.budget, delay=args.delay))
    elif args.cmd == "tools":
        _emit(P.tools_payload())
    elif args.cmd == "cocs":
        _emit(P.cocs_payload())
    elif args.cmd == "guard":
        from agent import planner
        with open(args.facts) as f:
            facts = json.load(f)
        with open(args.text) as f:
            text = f.read()
        allowed = "\n".join(f"- {k}: {v}" for k, v in facts.items())
        grounded = planner.numbers_are_grounded(text, allowed)
        _emit({"grounded": grounded,
               "verdict": "ok" if grounded else "rejected: contains a figure not in the engine output"})


if __name__ == "__main__":
    main()
