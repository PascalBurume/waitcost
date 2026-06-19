# Design prompt — WaitCost (high-fidelity prototype)

Paste everything below into Claude Design. It is self-contained.

---

You are designing a **high-fidelity, interactive prototype** for **WaitCost — "The Cost of
Doing Nothing"**, a decision-support web app for U.S. city budget directors and homelessness
agency leaders (Continuum-of-Care directors). It answers one expensive question: *"If we delay
funding homelessness intervention, what will the delay cost us?"* — with real government data,
honest uncertainty, an AI that explains itself, and a hard rule that a human, not the AI, makes
the final call.

This is a civic / public-policy analytics tool. The mood is **authoritative, humane, and
trustworthy** — think Our World in Data / USAFacts / a beautifully-restrained government data
product, NOT a flashy startup SaaS dashboard and NOT alarmist. Data and uncertainty are
first-class citizens. Every number shows its source and a range.

## Visual system
- **Palette:** warm off-white canvas (#FAFAF7-ish) with deep ink text; one calm, confident
  primary accent (a civic indigo/blue, e.g. #1A56DB) used for "act now"; neutral warm gray for
  "status quo / do nothing"; a controlled, *non-alarmist* amber→clay for "cost of waiting" and
  "over-represented" (used sparingly, never fire-engine red). Add a full dark mode.
- **Data-viz palette:** colorblind-safe, max 3 hues per chart, gray for neutral/structural.
- **Typography:** a clean modern grotesk for UI (e.g. Inter), and a readable humanist **serif for
  the decision brief / editorial copy** (gives it a "policy memo" gravitas). Two weights only.
- **Form:** generous whitespace, strong typographic hierarchy, soft 8–12px radii, hairline
  borders, flat surfaces (no heavy shadows/gradients), large legible numbers for headline stats.
- **Accessibility is mandatory:** WCAG 2.1 AA contrast, visible focus states, keyboard nav,
  charts readable without color alone. This is government data — accessibility is part of the pitch.

## App shell (persistent)
- Top bar: product mark "WaitCost", a **City selector** (dropdown of 17 U.S. cities, Los Angeles
  default), a small **data-vintage chip** ("HUD 2024 PIT · Census ACS 2024 (API)"), and a persistent,
  quiet **disclaimer line**: *"Informs a budget-timing tradeoff. Does not decide allocations or
  forecast individuals. All figures are ranges."*
- Primary nav (tabs or left rail): **Ask · Explore · Visualize · Where's the AI · Equity ·
  Governance · Map.**

## Screens (design all of these)

**1. Ask (the hero).** A single natural-language input ("Ask about waiting, budgets, who's
affected…"). On submit, show a **live "agent thinking" timeline** that streams steps —
`Understanding the question → Running 3 scenarios (Monte Carlo) → Backtesting → Explaining` —
each with a tier badge, visibly *pausing* at any Tier-2 step. Then reveal:
  - a large **Direct Answer card** (the headline number + its 80% range, plain-English sentence),
  - the **recommended chart** auto-rendered beneath it,
  - collapsible **"Agent trajectory"** (tool calls + Action Tier) and **full decision brief**
    (rendered in the serif, like a one-page policy memo).
  Design the **declined state** too: a calm, respectful card when the agent refuses an
  out-of-scope question ("I work at the city level and don't profile individuals").
  Design the **Tier-2 human-approval modal**: "Recommending a specific allocation needs your
  sign-off" with an explicit approve checkbox.

**2. Explore.** Sliders for **annual budget, years of delay, intervention mix** (prevention /
rapid-rehousing / supportive housing). A large **cost-trajectory fan chart**: three lines
(Status quo, Act now, Delay) each with a shaded P10–P90 uncertainty band, over a 10-year x-axis.
Three KPI stat cards. An "assumption sensitivity" strip showing the headline as a **range under
±50% of the (low-confidence) intervention effects** — honesty as a feature.

**3. Visualize.** A gallery/picker of 18 decision charts (cost trajectory, cost-of-waiting
waterfall, break-even curve, scenario bars, compartments-over-time area, budget comparison, mix
comparison, sensitivity tornado, SHAP drivers, backtest dot-interval, city scatter, city
benchmark, US map, equity disparity, equity unsheltered). Selecting one renders it large with a
caption and a source line. Make the charts genuinely beautiful and legible.

**4. Where's the AI.** A "model card": headline metric tiles (held-out R², the ML-vs-HUD-SPM
cross-check), a **SHAP horizontal bar** (housing cost on top), a **scatter** of 17 cities
(housing cost vs homelessness rate, selected city highlighted), and a **backtest** dot+interval
chart (predicted 2024 band vs the observed dot sitting inside it). Tone: "here's how the model
works, and here's proof it matched reality."

**5. Equity.** The differentiator. A **disproportionality chart** (which groups are
over-represented among the homeless vs. their population share; bars past 1.0× highlighted) and
an **unsheltered-rate-by-group** chart. A prominent, tasteful callout: *"Population-level only —
this never profiles individuals."* Make this screen feel weighty and respectful, not clinical.

**6. Governance.** An **Action Tiers** table (Tier 0–1 automatic; Tier 2 human approval), an
interactive **"data sufficiency" demo** (toggle a thin-data condition → the app shows it
*declining* rather than guessing), a data-sources list, and a short lifecycle/recalibration note.

**7. Map.** A U.S. map with **17 city bubbles** sized by homelessness rate per 1,000; clicking a
bubble selects that city app-wide. For the selected city, show its area highlighted with its
headline numbers. This is a strong "wow" landing/overview view.

## Signature "wow" moments to nail
1. The **live agent-thinking stream** with the Tier-2 *pause* — shows AI reasoning + the human gate.
2. **Uncertainty everywhere** — shaded bands, whiskers, ranges; never a naked point estimate.
3. The **map → city drilldown** re-skinning every screen to that city.
4. The **equity reveal** — a quietly powerful "who bears this" moment.

## Use this REAL data so screens look credible (don't invent numbers)
- Default city: **Los Angeles (CA-600)** · 71,201 people homeless (21,692 sheltered, 49,509
  unsheltered, 29,823 chronically homeless) · population 9.76M · median home value $866,500 ·
  poverty 13.3%.
- Headline (wait 3 years on a $15M program): **cost of waiting ≈ $345.6M more** over 10 years
  (80% range **$282M–$411M**); status-quo 10-yr public cost ≈ **$49.8B** (range $39.7B–$63.9B);
  acting now saves vs nothing.
- Learned model: **Ridge, held-out (leave-one-CoC-out) R² ≈ 0.36**; top **SHAP** driver =
  *median home value*; model-predicted inflow **2,817/mo** vs **HUD SPM 2,485/mo** (~13% apart).
- Backtest: predicted 2024 ≈ **68,500** (range 65,006–72,536) vs **observed 71,201** (~4% error,
  inside the band).
- Equity (over-representation among the homeless vs population share): **Los Angeles — Black 4.0×**;
  **Minneapolis — Native American/Alaska Native 10.1×**; **Chicago — Hispanic 2.45×**; **Seattle —
  AIAN 4.5×**. LA unsheltered-rate by group: Black 58.9%, White 77.7%, AIAN 84.8%.
- System facts to surface in the UI: **17 cities**, **4 AI agents** (analyst + visualization +
  city-brief + decision), **18 charts**, runs **fully offline**.

## Backend it will wire to (so design realistic states)
JSON API endpoints already exist: `POST /ask`, `POST /scenario`, `GET /model`, `GET /backtest`,
`GET /equity?coc=`, `GET /context?coc=`, `GET /charts`, `GET /chart?name=`, `GET /cocs`,
`GET /tools`. Design loading, success, empty, declined, and error states for each major view.

## Hard rules / what to avoid
- Always show ranges, never fake precision. Always show a source line on charts.
- Keep the "informs, does not decide" disclaimer visible; design the human-approval gate as a
  first-class, dignified interaction (not a nag).
- No individual-level or neighborhood-level data anywhere. No alarmist red, no dark patterns.
- Avoid generic SaaS-template look; this should feel like a credible public-interest instrument.

## Deliverables
High-fidelity desktop screens for all 7 views (responsive down to tablet), the key interaction
states above (thinking-stream, answer, declined, Tier-2 modal, slider-driven chart updates,
map drilldown), light + dark mode, and a small component/style spec (color tokens, type scale,
chart styles, stat card, KPI tile, agent-step item, disclaimer bar).
