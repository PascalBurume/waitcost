"""LLM provider seam: Claude Sonnet 4.6 via the Anthropic API.

This is the single place WaitCost talks to the language model. The planner and
the narrators call `generate(...)`; nobody else imports `anthropic`. On a missing
key or any API error `generate` returns None, and every caller already has a
deterministic fallback (rule-based plan / template brief), so a down API — or no
key at all — degrades to the offline path instead of breaking the demo.

The brain got smarter; the cage didn't move. Every figure the model writes still
passes the number-guard, and every dollar still passes the Tier-2 human gate —
both downstream of this module.
"""
import os

# Sonnet 4.6: strong routing + analyst-grade prose, and (unlike Opus 4.7/4.8) it
# still accepts temperature=0, so the demo stays deterministic. Override only to
# pin a different Claude model.
MODEL = os.environ.get("WAITCOST_CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_TIMEOUT = float(os.environ.get("CLAUDE_TIMEOUT", "30"))

_client = None


def claude_available():
    """True iff an Anthropic API key is present in the environment."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        import anthropic  # lazy: keep the dependency optional for the offline/rule path
        # One retry keeps latency bounded for a live demo; the SDK default is two.
        _client = anthropic.Anthropic(timeout=CLAUDE_TIMEOUT, max_retries=1)
    return _client


def generate(system, prompt, *, want_json=False, temperature=0.0, max_tokens=512):
    """Run Claude on (system, prompt) and return the text, or None on any failure.

    `want_json` is advisory — callers parse the first {...} themselves (mirrors the
    old Ollama path), so a partial or over-wrapped response still works. Returns
    None when no key is set or the API errors, so callers fall back to their
    deterministic output rather than crash.
    """
    if not claude_available():
        return None
    try:
        resp = _get_client().messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return None
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return text or None


def run_tool_loop(system, user, tools, execute, *, on_event=None, max_iters=8,
                  max_tokens=1024, client=None):
    """Manual Anthropic tool-use loop — the Phase-2 agentic reasoning trace.

    Claude is given `tools` and decides which to call; for each tool call we run
    `execute(name, args) -> str` (the REAL engine), feed the result back, and let
    Claude chain more calls or write its synthesis. Returns the final assistant
    text, or None when unavailable.

    Determinism comes from the seeded engine, not the sampler, so we leave
    temperature unset and run adaptive thinking (the streamed "where's the AI?"
    reasoning). `on_event(kind, payload)` surfaces the trace; kinds are
    "thinking" | "tool_use" | "tool_result" | "text". `client` is injectable so
    the loop is testable without a network call.
    """
    if client is None:
        if not claude_available():
            return None
        client = _get_client()

    def emit(kind, payload):
        if on_event is not None:
            try:
                on_event(kind, payload)
            except Exception:
                pass   # a broken consumer must never break the loop

    messages = [{"role": "user", "content": user}]
    final_text = ""
    for _ in range(max_iters):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                # Adaptive thinking is on; the raw chain of thought is summarized.
                thinking={"type": "adaptive", "display": "summarized"},
                messages=messages,
            )
        except Exception:
            return final_text or None

        tool_results = []
        for b in resp.content:
            bt = getattr(b, "type", None)
            if bt == "thinking":
                emit("thinking", getattr(b, "thinking", "") or "")
            elif bt == "text":
                final_text += b.text
                emit("text", b.text)
            elif bt == "tool_use":
                args = b.input or {}
                emit("tool_use", {"name": b.name, "input": args})
                try:
                    result = execute(b.name, args)
                    is_error = False
                except Exception as e:
                    # A gate (e.g. Tier-2 TierViolation) surfaces as a tool error the
                    # model can react to — the agent wanted to act and was stopped.
                    result = f"{type(e).__name__}: {e}"
                    is_error = True
                emit("tool_result", {"name": b.name, "result": result, "is_error": is_error})
                tool_results.append({"type": "tool_result", "tool_use_id": b.id,
                                     "content": str(result), "is_error": is_error})

        # Echo the assistant turn back verbatim (thinking blocks included — required
        # to continue the conversation on the same model).
        messages.append({"role": "assistant", "content": resp.content})
        if getattr(resp, "stop_reason", None) != "tool_use":
            break
        messages.append({"role": "user", "content": tool_results})

    return final_text or None
