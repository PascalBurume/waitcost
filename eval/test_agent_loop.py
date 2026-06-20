"""Phase 2 — agentic tool-use loop, verified without a live API.

A FakeClient scripts the Anthropic message sequence so the manual tool loop
(agent/llm.run_tool_loop) and its orchestrator integration are exercised
deterministically: real registry tools, real engine numbers, and the Tier-2 gate
firing before execution. conftest pins WAITCOST_PLANNER=rule.
"""
import os

from agent import capabilities as caps
from agent import llm
from agent.orchestrator import WaitCostAgent

PARAMS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "config", "params.yaml")


# --- a scriptable stand-in for anthropic.Anthropic --------------------------
class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _tool_use(tid, name, inp):
    return _Block(type="tool_use", id=tid, name=name, input=inp)


def _text(t):
    return _Block(type="text", text=t)


def _thinking(t):
    return _Block(type="thinking", thinking=t)


class _Resp:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class FakeClient:
    """Returns the scripted responses in order; records the create() kwargs."""
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    class _Messages:
        def __init__(self, outer):
            self.outer = outer

        def create(self, **kw):
            self.outer.calls.append(kw)
            return self.outer._scripted.pop(0)

    @property
    def messages(self):
        return FakeClient._Messages(self)


# --- the registry emits Anthropic tool schemas (third consumer, no drift) ----
def test_anthropic_tools_derive_from_registry():
    tools = caps.anthropic_tools()
    names = {t["name"] for t in tools}
    # every tool is an engine-running, handler-backed intent
    handler_intents = {c.intent for c in caps.REGISTRY if c.runs_engine and c.handler}
    assert names == handler_intents
    # non-engine intents never become tools
    assert {"greeting", "out_of_scope", "clarify"}.isdisjoint(names)
    by_name = {t["name"]: t for t in tools}
    cow = by_name["cost_of_waiting"]["input_schema"]
    assert cow["type"] == "object"
    assert set(cow["properties"]) == {"budget_musd", "delay_years"}
    assert "budgets" in by_name["compare_budgets"]["input_schema"]["properties"]


# --- the loop driver: tool_use -> execute -> tool_result -> synthesis --------
def test_run_tool_loop_executes_tools_and_streams_events():
    executed = []

    def execute(name, args):
        executed.append((name, dict(args)))
        return f"{name} ran"

    events = []
    scripted = [
        _Resp([_thinking("first cost_of_waiting, then synthesize"),
               _tool_use("t1", "cost_of_waiting", {"budget_musd": 15, "delay_years": 3})],
              stop_reason="tool_use"),
        _Resp([_text("Waiting is costly; act now.")], stop_reason="end_turn"),
    ]
    out = llm.run_tool_loop("sys", "q", caps.anthropic_tools(), execute,
                            on_event=lambda k, p: events.append((k, p)),
                            client=FakeClient(scripted))
    assert executed == [("cost_of_waiting", {"budget_musd": 15, "delay_years": 3})]
    assert "act now" in out
    kinds = {k for k, _ in events}
    assert {"thinking", "tool_use", "tool_result", "text"} <= kinds


# --- orchestrator integration: real engine numbers, grounded by construction -
def test_toolloop_trace_uses_the_real_engine(monkeypatch):
    monkeypatch.setenv("WAITCOST_AGENT", "toolloop")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")     # claude_available() -> True
    scripted = [
        _Resp([_tool_use("t1", "cost_of_waiting", {"budget_musd": 15, "delay_years": 3})],
              stop_reason="tool_use"),
        _Resp([_text("The engine shows waiting is costly.")], stop_reason="end_turn"),
    ]
    monkeypatch.setattr(llm, "_get_client", lambda: FakeClient(scripted))

    agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1)
    res = agent.answer("What if we wait 3 years on a $15M program?", out_dir="outputs")

    trace = res["agent_trace"]
    assert trace and trace["summary"]
    results = [s["payload"]["result"] for s in trace["steps"] if s["kind"] == "tool_result"]
    assert results and any("$" in r for r in results), "tool result must carry a real engine figure"


def test_toolloop_tier2_is_intercepted_before_execution(monkeypatch):
    monkeypatch.setenv("WAITCOST_AGENT", "toolloop")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    scripted = [
        _Resp([_tool_use("t1", "recommend_allocation", {"budget_musd": 50})],
              stop_reason="tool_use"),
        _Resp([_text("A human must approve that allocation.")], stop_reason="end_turn"),
    ]
    monkeypatch.setattr(llm, "_get_client", lambda: FakeClient(scripted))

    # An engine-path question reaches the trace; the scripted reply drives the
    # Tier-2 tool call regardless of the question text.
    agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1)
    res = agent.answer("What if we wait 3 years on a $50M program?", out_dir="outputs")  # no approval

    trace = res["agent_trace"]
    tool_results = [s["payload"] for s in trace["steps"] if s["kind"] == "tool_result"]
    assert tool_results and tool_results[0]["is_error"], "Tier-2 call must surface as a gated error"
    assert "TierViolation" in tool_results[0]["result"]


def test_toolloop_agent_picks_a_chart(monkeypatch):
    monkeypatch.setenv("WAITCOST_AGENT", "toolloop")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    scripted = [
        _Resp([_tool_use("t1", "cost_of_waiting", {"budget_musd": 15, "delay_years": 3})],
              stop_reason="tool_use"),
        _Resp([_tool_use("t2", "pick_chart", {"chart": "cost_of_waiting"})],
              stop_reason="tool_use"),
        _Resp([_text("Acting now is the call; the waterfall makes the penalty clear.")],
              stop_reason="end_turn"),
    ]
    monkeypatch.setattr(llm, "_get_client", lambda: FakeClient(scripted))

    agent = WaitCostAgent(PARAMS_PATH, memory_path="MEMORY.md", max_auto_tier=1)
    res = agent.answer("What if we wait 3 years on a $15M program?", out_dir="outputs")
    assert res["agent_trace"]["chosen_chart"] == "cost_of_waiting"
