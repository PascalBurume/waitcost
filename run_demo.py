"""End-to-end demo: ask the WaitCost agent a question, get a decision brief.

Run from the repo root:
    python run_demo.py
    python run_demo.py "What if we wait 3 years on a $15M program?"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.orchestrator import WaitCostAgent  # noqa: E402


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "What if we wait 5 years to intervene?"
    agent = WaitCostAgent("config/params.yaml", memory_path="MEMORY.md", max_auto_tier=1)
    result = agent.answer(question, out_dir="outputs")

    print("=" * 72)
    print(result["brief_markdown"])
    print("=" * 72)
    print("Planner used:", result["plan"]["planner"])
    print("Trajectory (skills called, with Action Tier):")
    for step in result["trajectory"]:
        print(f"  - {step['skill']:<20} tier={step['tier']} approved={step['approved']}")
    print("\nArtifacts written:")
    for fmt, path in result["artifacts"].items():
        print(f"  - {fmt}: {path}")


if __name__ == "__main__":
    main()
