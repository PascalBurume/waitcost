# 3–5 min video — shot list (WaitCost / CA-600)

Goal: make the **AI reasoning visible** (35%) and land the **responsible-AI tradeoff** (10%).
Lead with the agent thinking, not the slide deck. Every number on screen is reproducible.

## 0:00–0:30 — The decision, framed (Problem Understanding 20%)
- On screen: the one-liner + the question typed into the terminal:
  `python run_demo.py "What if we wait 3 years on a $15M program?"`
- Say: "A Los Angeles budget office has to decide *when* to fund. Our agent quantifies the
  compounding public cost of waiting — for **CA-600, Los Angeles**, on **real HUD + Census data**."
- Say the non-goal out loud: "It informs the timing tradeoff. It does **not** decide allocations
  or predict any individual."

## 0:30–1:30 — Where's the AI? The learned inflow model (AI Reasoning 35% — spend the most here)
- On screen: `python scripts/train_inflow.py` output, then the brief's
  "Where's the AI? Learned inflow predictor" section.
- Walk the four-part answer judges look for, pointing at it on screen:
  - **Inputs (named, real):** Census ACS economic signals — median home value, income, poverty,
    density — for the county of each CoC.
  - **Training signal (named, real):** HUD 2024 PIT homeless counts across **17 Continuums of Care**.
  - **Model + metric:** Ridge selected over gradient-boosted stumps by **leave-one-CoC-out CV**;
    honest held-out **R² ≈ 0.45** (not the in-sample 0.89 — show you didn't cherry-pick).
  - **Explainability:** the **SHAP** table — *housing cost (median home value)* is the dominant
    driver, matching the "homelessness is a housing problem" literature.
- Punchline: "The model's prediction **and its uncertainty band** set the simulator's inflow, so
  the cost ranges you'll see are partly **learned**, not hand-waved."

## 1:30–2:30 — The answer, with uncertainty (Impact & Insight 15%)
- On screen: the scenarios table + cost-of-waiting line.
- Say: "Waiting 3 years costs **$622.8M more** over the horizon — **range $495.9M–$797.3M**.
  Acting now vs. nothing saves ~**$1.5B**." Emphasize: **every dollar figure carries a P10–P90 band.**
- Point at the trajectory printout: "These came from the simulator — the agent called
  `run_simulation`, it didn't invent them. A unit test fails if the brief and simulator ever disagree."

## 2:30–3:30 — Responsible AI tradeoff (Responsible AI 10% — the part to nail)
- Pick **ONE** tradeoff and show it concretely on screen (don't list all of F1–F8):
  - **The transparency vs. precision tradeoff.** Show the brief's **Limitations** + the
    `confidence: low` tags in `params.yaml`. Say: "We *could* have shipped tighter-looking
    point estimates. We refused. Transition rates aren't yet fit to HUD SPM flow data, so we
    label them low-confidence and widen the bands rather than overclaim."
  - Then the **human gate**: run the Tier-2 path and show `TierViolation` — "Recommending an
    allocation is Tier-2: the agent **stops and asks a human**. There's a test that enforces it."
  - Then the **scope/bias honesty**: show the NYC scope note — "the model under-predicts
    right-to-shelter cities; we surface that residual instead of hiding it."

## 3:30–4:30 — Lifecycle / the grad differentiator (Solution Design 20% + Responsible AI)
- On screen: `MEMORY.md` audit entry, `GOVERNANCE.md`, `data/SOURCES.md`.
- Say: "Every brief is traceable to a data vintage in `MEMORY.md`. `GOVERNANCE.md` names the
  recalibration cadence — **re-fit when the next HUD PIT/SPM lands** — and drift detection.
  Our **named next step** is calibrating the flow rates from HUD SPM; the architecture is already
  built for it." End on the eval harness: `pytest` → **14/14**, including the anti-fabrication test.

## Do / Don't
- DO show real terminal output and the brief; DO say the held-out metric and the band out loud.
- DON'T narrate the model's internal chain-of-thought; show reasoning through the **agent's
  trajectory + brief**. DON'T present any number without its range.
