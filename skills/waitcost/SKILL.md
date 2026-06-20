---
name: waitcost
description: >-
  Estimate the public cost of DELAYING homelessness intervention in a US city
  (Continuum of Care). Use when the user asks about the cost of waiting,
  break-even timing, return on investment, savings from acting now, cost per
  person helped, projected outcomes at the 10-year horizon, comparing annual
  budgets or intervention mixes, population-level equity disparities, or ranking
  the cost of inaction across cities. Runs a deterministic, offline
  system-dynamics simulator over real HUD Point-in-Time + Census ACS data. It
  INFORMS a budget-timing tradeoff — it does NOT decide allocations or forecast
  individuals, and it cannot answer questions about named individuals or sub-city
  geographies.
---

# WaitCost — cost-of-inaction analyst

WaitCost answers "what does waiting cost?" for homelessness budget timing. Every
figure comes from a Python simulator calibrated on real public data; your job is
to route the question, run the bundled CLI, and report the engine's numbers — not
to compute or estimate any figure yourself.

## When to use

Route the user's question to one analysis (the CLI's `ask` picks the intent
automatically — you pass the raw question):

- **cost_of_waiting** — extra 10-year public cost of waiting N years (the default)
- **break_even** — how long the city can wait before delaying stops paying off
- **savings_now** — how much acting now saves vs. doing nothing
- **roi** — benefit–cost ratio of acting now (avoided cost per $ spent)
- **cost_per_person** — people kept out of homelessness, and avoided cost per head
- **outcome_at_horizon** — projected people homeless at the 10-year horizon
- **compare_budgets** / **compare_mix** — compare annual budgets / intervention mixes
- **uncertainty** / **sensitivity** — how confident the headline is, what drives the band
- **equity** — population-level racial/demographic disparities (never individuals)
- **regional** — rank the cost of waiting across multiple cities
- **city_context** — plain profile of a city's homelessness + housing situation

Do **not** use WaitCost for named individuals, households, or sub-CoC geographies
(neighborhoods, ZIP codes, streets) — the CLI will decline these, and so should you.

## Prerequisites (one-time)

This skill drives the WaitCost Python engine in this repository. Ensure its deps
are installed once: `pip install -r requirements.txt` from the repo root
(`inactioncost/`). No API key and no network are needed — the engine is offline.

## How to run

Always call the bundled CLI; it returns JSON. **Never introduce, round, or
recompute a dollar figure** — echo only numbers present in the CLI output.

```bash
python skills/waitcost/scripts/waitcost_cli.py ask "What if we wait 3 years on a $15M program?" --coc CA-600
```

The `ask` result includes: `intent`, `direct_answer` (the engine's headline —
quote this), `runs` (status_quo / act_now / delay cost bands), `comparison`
(cost of waiting, savings, break-even), `drivers`, `recommended_chart`,
`brief_markdown`, and `artifacts`. If the result has `"declined": true`, relay
the `reason` — do not work around a decline.

### Subcommands

- `ask "<question>" [--coc CA-600]` — full agent loop (intent routing + brief)
- `chart <name> [--coc --budget --delay]` — a render-ready chart spec (JSON)
- `tools` — the capability catalog + counts (5 agents · capabilities · charts)
- `cocs` — the cities the engine supports
- `guard --facts facts.json --text memo.txt` — self-check a memo for invented numbers

To recommend the matching visual, read `recommended_chart` from `ask`, then call
`chart <that-name>` with the same `--coc/--budget/--delay`; its numbers match the
text by construction.

## Action tiers (enforced in code, not advisory)

Tier 0/1 analyses run automatically. **Tier 2** — recommending a *specific
binding allocation* — requires explicit human approval. The CLI runs at
`max_auto_tier=1`, so a Tier-2 step RAISES unless you pass `--approve-allocation`.
Only pass that flag after the user has explicitly confirmed they want a binding
recommendation. Otherwise, present the analysis and let the human decide. See
`reference/GOVERNANCE.md`.

## Number-guard

The engine is the single source of truth for every number. When you write a
summary, use only figures from the CLI JSON. If you are unsure whether a memo you
drafted stays faithful, verify it: write the engine `facts` to `facts.json` and
your memo to `memo.txt`, then run `guard --facts facts.json --text memo.txt`; a
`"grounded": false` verdict means you introduced a figure the engine never
produced — fix it before sending.

## Limitations (state these when relevant)

- Calibrated for CA-600 (Los Angeles) on real data; other cities reuse CA-600
  flow-rate priors and are illustrative until locally calibrated.
- All outputs are ranges, not point predictions; the sign (waiting costs more) is
  robust, the magnitude is a planning estimate.
- The tool informs a budget-timing tradeoff; it does not decide allocations,
  forecast individuals, or surface anything below the population level.
