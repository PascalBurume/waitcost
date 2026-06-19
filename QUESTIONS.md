# What you can ask WaitCost

> Auto-generated from the app's capability registry (`python scripts/gen_questions.py`). Every type below is something the app actually routes and answers.

**Two things to know first:**

- Questions apply to the **city you've selected** (Los Angeles / CA-600 by default — switch cities in the app header). Some types let you name a city in the question.
- Every dollar figure is a **range, not a point** — the model reports the 80% range and is explicit about what's calibrated vs. assumed.

## Cost & timing

_The core: what delay costs, when it stops paying off, what acting now buys._

### Cost of Waiting
Extra 10-year public cost of waiting N years before acting, with a range.

- “What does it cost to wait 3 years?”
- “What's the extra cost of waiting 5 years on $15M?”
- “How much more does it cost if we wait two years?”
- “What if we delay?”

**You get:** a quantified estimate with an **80% range**, plus the **cost_of_waiting** chart.

### Break-even
How long the city can wait before delaying stops paying off.

- “How long can we wait before it stops paying off?”
- “When does waiting stop being worth it?”
- “What's the break-even year?”
- “How many years can we afford to delay?”
- “What's the latest we can act and still come out ahead?”

**You get:** a quantified estimate with an **80% range**, plus the **break_even_curve** chart.

### Savings Now
How much acting now saves (or costs) vs doing nothing.

- “How much do we save by acting now?”
- “What are the savings of acting now versus nothing?”
- “What's the benefit of acting now?”
- “How much money does acting today save us?”

**You get:** a quantified estimate with an **80% range**, plus the **scenario_costs** chart.

### People homeless at the horizon
Projected number of people homeless at the 10-year horizon.

- “How many people will be homeless in 2034?”
- “What's the projected homeless count at the horizon?”
- “How many people end up homeless if we do nothing?”

**You get:** a quantified estimate with an **80% range**, plus the **people_helped** chart.

### Cost per Person
People kept out of homelessness by acting now, and avoided public cost per person.

- “How many people would acting now help?”
- “What is the cost per person helped?”
- “How many people can we keep off the street?”
- “How many people housed per dollar?”
- “What's the avoided cost per capita?”

**You get:** a quantified estimate with an **80% range**, plus the **people_helped** chart.

### ROI
Return on investment / benefit-cost ratio of acting now (avoided cost per $ spent).

- “What's the ROI on a $15M program?”
- “Is it worth the investment?”
- “What's the benefit-cost ratio?”
- “Do we get our money back?”
- “What's the return per dollar spent?”

**You get:** a quantified estimate with an **80% range**, plus the **roi** chart.

## Comparisons

_Put options side by side._

### Compare Budgets
Compare two or more annual budgets by 10-year cost and savings.

- “Is $15M or $50M the better budget?”
- “Compare a $10M and a $30M annual budget.”
- “$20M versus $40M — which wins?”
- “Which is better, $15M or $25M a year?”

**You get:** a quantified estimate with an **80% range**, plus the **budget_comparison** chart.

### Compare Mix
Compare prevention / rapid-rehousing / supportive-housing spending mixes.

- “Should we fund prevention or supportive housing?”
- “Prevention vs rapid re-housing?”
- “What mix of programs should we fund?”
- “How should we split between interventions?”
- “Is PSH or prevention the better use of funds?”

**You get:** a quantified estimate with an **80% range**, plus the **mix_comparison** chart.

### Across cities
Rank the cost of waiting across multiple cities (same engine, real per-city data).

- “Which cities pay the most for waiting?”
- “Rank the cities by cost of inaction.”
- “Compare the cost of waiting across all CoCs.”
- “Where is it worst across the region?”
- “Which city is the costliest to delay in?”

**You get:** a quantified estimate with an **80% range**, plus the **regional_waiting** chart.

## Confidence & drivers

_How much to trust the number, and what moves it._

### Uncertainty
How confident the headline is: the range, the weakest assumption, the backtest error.

- “How confident are you in that number?”
- “Can we trust this estimate?”
- “How wide is the range?”
- “What's the margin of error?”
- “Explain how reliable that figure is.”

**You get:** a quantified estimate with an **80% range**, plus the **sensitivity_tornado** chart.

### Sensitivity
Which assumption the result is most sensitive to (what to tighten first).

- “Which assumption matters most?”
- “What drives the result?”
- “Which assumption are we least sure about?”
- “What should we tighten first?”

**You get:** a quantified estimate with an **80% range**, plus the **sensitivity_tornado** chart.

## Equity

_Who bears homelessness — population level only._

### Equity
Population-level racial/demographic disparities (who bears homelessness, who is most unsheltered) — never profiles individuals.

- “What are the racial disparities in homelessness?”
- “Who bears homelessness most by race?”
- “Is there demographic over-representation?”
- “Which racial group is most unsheltered?”
- “Show me equity by ethnicity.”

**You get:** a quantified estimate with an **80% range**, plus the **equity_disparity** chart.

## City context & definitions

_Background, not a calculation — grounded in cited sources._

### City Situation
A richer grounded narrative brief of a city's homelessness situation (grounded context with citations, not the cost model).

- “What's the homelessness situation in Seattle?”
- “Tell me about Seattle.”
- “Give me an overview of homelessness here.”
- “How bad is homelessness in this city?”
- “What's happening with homelessness here?”

**You get:** a grounded, **cited** city narrative (general context, not the cost model).

### Care Plan
The city's strategy, care plan, response, or what they are doing about homelessness (grounded context, not the cost model).

- “What is San Diego's plan?”
- “What is the city's strategy?”
- “What are they doing about homelessness?”
- “How is the city responding to homelessness?”
- “What initiatives are in place?”

**You get:** a grounded, **cited** city narrative (general context, not the cost model).

### City snapshot
Plain-language numeric profile of a city's homelessness + housing indicators.

- “Show me the housing profile.”
- “What are the housing indicators?”
- “How expensive is housing here?”
- “Give me the cost-of-living snapshot.”
- “City benchmark numbers, please.”

**You get:** a quantified estimate with an **80% range**, plus the **city_benchmark** chart.

### Concept Q&A
A definitional or 'why' question about a homelessness concept or term (grounded, cited context — not the cost model).

- “What is rapid re-housing?”
- “What is permanent supportive housing?”
- “What does chronic homelessness mean?”
- “Why does housing cost drive homelessness?”

**You get:** a plain-English, **cited** answer — no simulation.

### Data & sources
A question about the underlying DATA — its source, vintage, recency, or methodology (not a calculation).

- “What data is this based on?”
- “How recent is the PIT count?”
- “What's the data vintage?”

**You get:** a plain-English, **cited** answer — no simulation.

## Getting started

_Say hello or ask what it can do._

### Greeting
Small-talk (hi/hello/thanks) OR a meta question about what the tool does (what can you do, who are you, help).

- “hi”
- “hello there”
- “good evening”
- “thanks!”
- “what can you do?”

**You get:** a short orientation to what you can ask.

## Power moves — compound questions

WaitCost answers a question as one *or more* tool calls, so you can pack several asks into one sentence:

- **Several budgets at once** — “What does it cost to wait 3 years on a **$15M and a $25M** program?” returns the cost of waiting for *each* budget, side by side, with a per-budget chart.
- **“…and…” means “answer each”**; **“which is better?” / “vs”** means “compare the totals” (e.g. “Is $15M **or** $50M better?”).
- Every value you mention is answered — the app never silently drops one. If it can't cover something, it says so.

## What WaitCost won't answer

By design, it answers at the **city (CoC) level** and **never about individuals**. These are politely declined:

- “Which family on 5th street will become homeless?”
- “Name the person who will lose their housing.”
- “Which individual is most at risk?”
- “What about the household at 12 Elm Street?”
- “Homelessness in zip code 90001?”

It also declines when the data can't support a credible answer (e.g. a city with too thin a count), rather than showing an unsupported number.
