"""Track B + registry-quality tests.

Track B: the bundled skill CLI must return the SAME numbers as the engine
(proving no divergence), must keep the Tier-2 gate, and ship a valid SKILL.md.
Plus a couple of registry-quality checks for the generated planner prompt.
"""
import json
import os
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLI = os.path.join(_REPO, "skills", "waitcost", "scripts", "waitcost_cli.py")
_SKILL_MD = os.path.join(_REPO, "skills", "waitcost", "SKILL.md")

_Q = "What if we wait 3 years on a $15M program?"


def _run_cli(*args):
    env = {**os.environ, "WAITCOST_PLANNER": "rule"}   # deterministic, no Ollama
    out = subprocess.check_output([sys.executable, _CLI, *args], cwd=_REPO, env=env)
    return json.loads(out)


# --- generated planner prompt (registry quality) ---------------------------
def test_plan_system_lists_all_intents():
    from agent import planner
    sys_prompt = planner.build_plan_system(10.0)
    for intent in planner.INTENTS:
        assert intent in sys_prompt, intent
    # at least one worked example survived generation
    assert "->" in sys_prompt and "cost_of_waiting" in sys_prompt


# --- Track B: CLI parity + safety ------------------------------------------
def test_waitcost_cli_ask_matches_engine_numbers():
    from api import payloads as P
    cli = _run_cli("ask", _Q)
    direct = P.ask_payload(_Q)   # same path the CLI wraps; rule planner is deterministic
    assert cli["intent"] == direct["intent"] == "cost_of_waiting"
    assert cli["runs"]["act_now"]["final_cum_cost_p50"] == \
        direct["runs"]["act_now"]["final_cum_cost_p50"]
    assert cli["comparison"]["cost_of_waiting"]["extra_cost_median"] == \
        direct["comparison"]["cost_of_waiting"]["extra_cost_median"]


def test_waitcost_cli_tools_reports_counts():
    tools = _run_cli("tools")
    assert tools["agents"] == 4
    # tools_payload overrides `capabilities` with the full catalog list; counts
    # are the list length + the chart count.
    assert len(tools["capabilities"]) == 16 and tools["charts"] == 18


def test_skill_md_frontmatter_valid():
    with open(_SKILL_MD) as f:
        text = f.read()
    assert text.startswith("---")
    fm = text.split("---", 2)[1]
    # name + description present; description states BOTH what and when
    assert "name: waitcost" in fm
    assert "description:" in fm
    desc = fm.split("description:", 1)[1].lower()
    assert "cost" in desc and "use when" in desc
    # the safety boundary is documented in the body
    assert "Tier 2" in text and "approve-allocation" in text


def test_cli_guard_rejects_invented_number(tmp_path):
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({"cost_of_waiting_median": "$42.0M"}))
    memo = tmp_path / "memo.txt"
    memo.write_text("Waiting costs about $42.0M, and we will house 9999 people.")
    res = _run_cli("guard", "--facts", str(facts), "--text", str(memo))
    assert res["grounded"] is False   # 9999 is not in the facts
