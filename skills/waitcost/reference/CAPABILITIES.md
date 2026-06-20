# WaitCost capabilities (generated)

> Generated from `agent/capabilities` by `scripts/gen_reference.py` — do not edit by hand.

| Intent | When to use | Params | Tier | Chart |
|---|---|---|---|---|
| `cost_per_person` | cost per person helped / how many people acting now helps | budget_musd | 1 | `people_helped` |
| `equity` | population-level racial/demographic disparities in who is homeless | coc | 0 | `equity_disparity` |
| `regional` | rank or compare the cost of inaction across MULTIPLE cities | budget_musd, delay_years | 1 | `regional_waiting` |
| `break_even` | how long can we wait before delaying stops paying off | budget_musd | 1 | `break_even_curve` |
| `compare_mix` | prevention vs rapid-rehousing vs supportive housing | budget_musd | 1 | `mix_comparison` |
| `compare_budgets` | compare budget amounts (fill budgets[]) | budgets | 1 | `budget_comparison` |
| `roi` | return on investment / benefit-cost ratio of acting now | budget_musd | 1 | `roi` |
| `savings_now` | savings of acting now vs nothing | budget_musd | 1 | `scenario_costs` |
| `outcome_at_horizon` | how many homeless later | — | 1 | `people_helped` |
| `uncertainty` | how confident/reliable the number is, or explain a figure's range | — | 0 | `sensitivity_tornado` |
| `sensitivity` | which assumption matters most | — | 0 | `sensitivity_tornado` |
| `city_context` | plain numeric profile of a city's homelessness/housing indicators (snapshot) | coc | 0 | `city_benchmark` |
| `cost_of_waiting` | extra cost of waiting | delay_years, budget_musd | 1 | `cost_of_waiting` |

Non-answerable intents the router also recognises: `greeting`, `out_of_scope`, `data_lookup`, `concept_qa`, `care_plan`, `city_situation`, `clarify` (greeting / clarify / decline — no engine run).

Infra capabilities (not routed to by the planner): `retrieve_us_context` (tier 0), `visualize` (tier 0), `recommend_allocation` (tier 2).
