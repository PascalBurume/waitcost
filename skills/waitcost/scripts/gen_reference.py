#!/usr/bin/env python3
"""Generate skills/waitcost/reference/CAPABILITIES.md from the live registry.

Keeps the skill's reference doc in lock-step with agent/capabilities so the
skill description and the engine never drift. Run from the repo root:
    python skills/waitcost/scripts/gen_reference.py
"""
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from agent import capabilities as caps   # noqa: E402

_OUT = os.path.join(os.path.dirname(__file__), "..", "reference", "CAPABILITIES.md")


def render():
    lines = [
        "# WaitCost capabilities (generated)",
        "",
        "> Generated from `agent/capabilities` by `scripts/gen_reference.py` — do not edit by hand.",
        "",
        "| Intent | When to use | Params | Tier | Chart |",
        "|---|---|---|---|---|",
    ]
    for c in caps.REGISTRY:
        if not c.in_catalog:
            continue
        params = ", ".join(c.params) or "—"
        lines.append(f"| `{c.intent}` | {c.when_to_use} | {params} | {c.catalog_tier} | "
                     f"`{c.chart or '—'}` |")
    lines += [
        "",
        "Non-answerable intents the router also recognises: "
        + ", ".join(f"`{c.intent}`" for c in caps.REGISTRY if not c.in_catalog)
        + " (greeting / clarify / decline — no engine run).",
        "",
        "Infra capabilities (not routed to by the planner): "
        + ", ".join(f"`{ic.name}` (tier {ic.tier})" for ic in caps.INFRA_CAPS) + ".",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    out = os.path.abspath(_OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(render())
    print("wrote", out)
