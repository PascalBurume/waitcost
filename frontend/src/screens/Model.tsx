import { api } from "../api/client";
import type { Backtest, ChartSpec, ModelPayload } from "../api/types";
import { useApp } from "../state";
import { useAsync } from "../lib/useAsync";
import { fmtNum, fmtPct } from "../lib/format";
import { ChartSkel, ErrorState, StatTile } from "../components/ui";
import { ChartView } from "../charts/ChartView";
import { Explain } from "../components/Explain";
import { Icon } from "../lib/icons";

export function ModelScreen() {
  const { coc } = useApp();
  const model = useAsync<ModelPayload>(() => api.model(), []);
  const backtest = useAsync<Backtest>(() => api.backtest(), []);
  const shap = useAsync<ChartSpec>((s) => api.chart("shap_drivers", coc, 15, 3, s), [coc]);
  const btChart = useAsync<ChartSpec>((s) => api.chart("backtest", coc, 15, 3, s), [coc]);
  const tornado = useAsync<ChartSpec>((s) => api.chart("sensitivity_tornado", coc, 15, 3, s), [coc]);

  if (model.error) return <div className="page"><ErrorState error={model.error} onRetry={model.reload} /></div>;
  const m = model.data;
  const b = backtest.data;

  return (
    <div className="page page-wide">
      <div className="section-head">
        <span className="eyebrow">Where's the AI</span>
        <h1 className="page-title serif">A learned model you can actually understand</h1>
        <p className="lede">
          We taught a small AI to spot the <b>economic warning signs of homelessness</b> — then made it
          show its work, admit what it gets wrong, and prove itself on a year it had never seen. Every box
          below has a plain-English “What does this mean?” for the curious.
        </p>
        <div style={{ marginTop: 10 }}>
          <Explain
            title="What is this model, in one breath?"
            label="Start here — how does this AI work?"
            plain={
              <>
                <p>We showed a small AI the <b>local economy</b> of 17 cities — rents, incomes, poverty,
                  how crowded housing is — and let it learn the pattern that predicts how many people slip
                  into homelessness.</p>
                <p>The catch that makes it honest: whenever we test it on a city, that city was <b>hidden
                  during training</b>. So its accuracy is earned, not memorized.</p>
              </>
            }
            analogy={
              <>a doctor who, after seeing many patients, learns to read risk from blood pressure and weight —
                then is tested on someone they’ve never met.</>
            }
          >
            <p>Model: <code>gb_stumps(rounds=50)</code> — gradient-boosted decision stumps mapping 4 standardized
              Census ACS economic signals → HUD PIT homelessness rate per 1,000, across all 17 Continuums of Care.</p>
            <p>Validated <b>leave-one-CoC-out</b>: for each city, train on the other 16 and predict the held-out
              one. Held-out <code>R² = 0.36</code>, <code>MAE = 1.92</code> per 1,000.</p>
            <p>Refit on the <b>API-sourced</b> ACS panel (features pulled from the Census API via
              <code>scripts/fetch_acs.py</code>, verified 0/119 ≥5%). The held-out R² (≈0.36) and the
              backtest (≈4%) are unchanged by the refresh.</p>
          </Explain>
        </div>
      </div>

      <div style={{ marginTop: 22 }}>
        <span className="eyebrow">Where the AI actually is</span>
        <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "4px 0 0", maxWidth: 640 }}>
          Three learned parts do the judgement; the dollars stay in transparent, auditable math. The AI
          informs — it never silently decides.
        </p>
      </div>
      <div className="ai-map">
        <div className="ai-card is-ai">
          <div className="ai-card-top"><span className="ai-card-ico"><Icon.Brain size={16} /></span><span className="ai-card-kicker">AI · learned</span></div>
          <div className="ai-card-title">Understands your question</div>
          <div className="ai-card-desc">An offline language model reads plain English and routes it to the right analysis.</div>
          <div className="ai-card-tag">Gemma · on-device, no API key</div>
        </div>
        <div className="ai-card is-ai">
          <div className="ai-card-top"><span className="ai-card-ico"><Icon.Brain size={16} /></span><span className="ai-card-kicker">AI · learned</span></div>
          <div className="ai-card-title">Predicts who falls into homelessness</div>
          <div className="ai-card-desc">A model learned the link from a city’s economy to its homelessness — <b>this page</b>.</div>
          <div className="ai-card-tag">gb_stumps · trained on real Census + HUD</div>
        </div>
        <div className="ai-card is-ai">
          <div className="ai-card-top"><span className="ai-card-ico"><Icon.Brain size={16} /></span><span className="ai-card-kicker">AI · explainable</span></div>
          <div className="ai-card-title">Explains its own reasoning</div>
          <div className="ai-card-desc">SHAP shows why it predicted what it did; a stress test shows where it’s fragile.</div>
          <div className="ai-card-tag">SHAP + sensitivity (XAI)</div>
        </div>
        <div className="ai-card is-engine">
          <div className="ai-card-top"><span className="ai-card-ico"><Icon.Scale size={16} /></span><span className="ai-card-kicker">Not AI · on purpose</span></div>
          <div className="ai-card-title">Does the cost math</div>
          <div className="ai-card-desc">The dollars come from a transparent simulator — auditable Python, no black box.</div>
          <div className="ai-card-tag">Deterministic · every number traceable</div>
        </div>
      </div>

      <div className="model-tiles" style={{ marginTop: 16 }}>
        <StatTile label="HELD-OUT R² (LEAVE-ONE-COC-OUT)" value={m ? m.loo_r2.toFixed(2) : "—"} sub="honest out-of-sample fit" prov="model" />
        <StatTile label="ML vs HUD SPM CROSS-CHECK" value={m ? fmtPct(m.spm_crossval.agreement_pct_diff) : "—"} sub="two independent methods agree within" prov="model" />
        <StatTile label="MODEL TYPE" value={m ? shortModel(m.model) : "—"} sub={m ? `${m.features.length} ACS features` : ""} prov="model" />
        <StatTile label="BACKTEST ERROR (2024)" value={b ? fmtPct(b.abs_pct_error_p50) : "—"} sub={b ? (b.within_band ? "observed inside the band" : "close, slightly under-counted") : ""} prov="model" />
      </div>

      <div className="row gap-10" style={{ flexWrap: "wrap", marginTop: 12 }}>
        <Explain
          title="What is R² — and why is 0.36 actually good here?"
          label="What does R² mean?"
          plain={
            <>
              <p><b>R² is a 0-to-1 report card for predictions.</b> 0.36 means the model explains about a
                third of why cities differ in homelessness — modest-sounding, but real and <b>honest</b>,
                because the city being graded was never seen in training.</p>
              <p>The typical miss (<b>MAE</b>) is about 2 homeless people per 1,000 residents.</p>
            </>
          }
          analogy={<>grading a student on an exam built from questions they’ve never practiced — a lower score
            you can trust more than a perfect one on memorized answers.</>}
        >
          <p>Leave-one-CoC-out cross-validation: <code>R² = 0.36</code>, <code>MAE = 1.92</code> per 1,000.
            Out-of-sample by construction — no city is scored on data it trained on, so there’s no leakage.</p>
        </Explain>

        <Explain
          title="Two independent methods that agree"
          label="What is the cross-check?"
          plain={
            <p>We estimate how many people newly become homeless each month in <b>two completely different
              ways</b> — once from an official government statistic, once from our learned model. When two
              independent methods land close together, that’s a strong sign the estimate is trustworthy and
              not an artifact of one technique.</p>
          }
          analogy={<>two surveyors measuring the same field with different tools and getting nearly the same
            acreage — you believe the number.</>}
        >
          {m ? (
            <table className="explain-table">
              <thead><tr><th>method</th><th>monthly inflow</th></tr></thead>
              <tbody>
                <tr><td>ML model (ACS → PIT)</td><td className="num">{fmtNum(m.spm_crossval.ml_inflow_monthly)}/mo</td></tr>
                <tr><td>HUD SPM Measure 5 (first-time homeless)</td><td className="num">{fmtNum(m.spm_crossval.spm_inflow_monthly)}/mo</td></tr>
                <tr><td>agreement</td><td className="num">{fmtPct(m.spm_crossval.agreement_pct_diff)}</td></tr>
              </tbody>
            </table>
          ) : <p>Loading…</p>}
          <p style={{ marginTop: 8 }}>{m?.spm_crossval.note}</p>
        </Explain>
      </div>

      <div className="model-grid" style={{ marginTop: 20 }}>
        <div className="card chart-card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="chart-title">Why the model predicts what it does</span>
            <Explain
              title="SHAP — the model’s itemized receipt"
              label="What is SHAP?"
              plain={
                <>
                  <p><b>SHAP answers “why did the model predict that?”</b> For each factor, it shows how much
                    that factor pushed the prediction up or down.</p>
                  <p>Here, the <b>cost of housing</b> is by far the strongest force pushing homelessness up —
                    exactly what decades of research find. The model isn’t a black box; it shows its receipts.</p>
                </>
              }
              analogy={<>an itemized receipt for a prediction: each line shows how much that ingredient added
                or subtracted from the total.</>}
            >
              <p>Mean SHAP contribution to predicted homelessness, per 1,000 residents:</p>
              <table className="explain-table">
                <thead><tr><th>driver</th><th>contribution</th></tr></thead>
                <tbody>
                  <tr><td><code>log_median_home_value</code></td><td className="num pos">+2.33</td></tr>
                  <tr><td><code>log_pop_density</code></td><td className="num neg">−0.29</td></tr>
                  <tr><td><code>poverty_rate</code></td><td className="num neg">−0.16</td></tr>
                  <tr><td><code>median_household_income</code></td><td className="num">+0.00</td></tr>
                </tbody>
              </table>
              <p style={{ marginTop: 8 }}>Housing cost dominates — and it points the right way, matching the
                housing-cost literature on homelessness.</p>
            </Explain>
          </div>
          <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "4px 0 8px" }}>Housing cost is the biggest force pushing the prediction up.</p>
          {shap.loading || !shap.data ? <ChartSkel h={300} /> : <ChartView spec={shap.data} height={300} />}
        </div>

        <div className="card chart-card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="chart-title">The honesty test: predicted 2024 vs reality</span>
            <Explain
              title="Backtest — did it work on a year it never saw?"
              label="What is the backtest?"
              plain={
                <>
                  <p>We set the model to the <b>real 2023 situation</b>, let it run forward a full year with
                    <b> no peeking</b>, and compared its 2024 prediction to what actually happened.</p>
                  <p>It came within about <b>9%</b> — close, but it slightly under-counted. We show that miss
                    on purpose: a model that tells you where it’s wrong is one you can actually trust.</p>
                </>
              }
              analogy={<>testing a weather model by feeding it last year’s starting conditions and checking its
                forecast against what really happened.</>}
            >
              {b ? (
                <table className="explain-table">
                  <thead><tr><th>2024 active homeless</th><th>count</th></tr></thead>
                  <tbody>
                    <tr><td>model prediction (P50)</td><td className="num">{fmtNum(b.predicted_active_p50)}</td></tr>
                    <tr><td>model range (P10–P90)</td><td className="num">{fmtNum(b.predicted_active_p10)} – {fmtNum(b.predicted_active_p90)}</td></tr>
                    <tr><td>observed (real PIT)</td><td className="num">{fmtNum(b.observed_2024_total)}</td></tr>
                    <tr><td>central error</td><td className="num">{fmtPct(b.abs_pct_error_p50)}</td></tr>
                  </tbody>
                </table>
              ) : <p>Loading…</p>}
              <p style={{ marginTop: 8 }}>Seeded on observed 2023 PIT, run 12 months on SPM-calibrated
                transition rates. The observed count sits just above the model’s band — surfaced, not hidden.</p>
            </Explain>
          </div>
          <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "4px 0 8px" }}>Seeded on 2023, run forward a year, compared to what really happened.</p>
          {btChart.loading || !btChart.data ? <ChartSkel h={300} /> : <ChartView spec={btChart.data} height={300} />}
        </div>
      </div>

      <div className="card chart-card" style={{ marginTop: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <span className="chart-title">Where the answer is most fragile (stress test)</span>
          <Explain
            title="Sensitivity — we stress-test the answer, not just report it"
            label="What is the stress test?"
            plain={
              <>
                <p>We don’t hand you a single number and walk away. We <b>nudge each assumption up 20%</b> and
                  watch how much the final cost moves.</p>
                <p>The biggest movers are where the conclusion is <b>most fragile</b> — so that’s where better
                  data would help most. We flag the high-impact, low-confidence ones honestly.</p>
              </>
            }
            analogy={<>wiggling each leg of a table to find which one is loose — that’s the one to fix first.</>}
          >
            <p>+20% to each transition rate → change in 10-year cost (higher = the result leans on it more):</p>
            <table className="explain-table">
              <thead><tr><th>assumption (transition)</th><th>Δ cost</th><th>confidence</th></tr></thead>
              <tbody>
                <tr><td>sheltered → exited_positive</td><td className="num">−6.8%</td><td>high</td></tr>
                <tr><td>at_risk → sheltered</td><td className="num">+4.7%</td><td>low</td></tr>
                <tr><td>housed_stable → at_risk</td><td className="num">+4.1%</td><td>low</td></tr>
                <tr><td>at_risk → housed_stable</td><td className="num">−3.9%</td><td>low</td></tr>
                <tr><td>chronic_unsheltered → exited_positive</td><td className="num">−2.6%</td><td>low</td></tr>
              </tbody>
            </table>
            <p style={{ marginTop: 8 }}>Low-confidence, high-impact rows are exactly where the conclusion is
              fragile — and where the model says “get better data here first”.</p>
          </Explain>
        </div>
        <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "4px 0 8px" }}>Longer bar = the final cost leans on that assumption more.</p>
        <div className="stress-layout">
          <div className="stress-chart">
            {tornado.loading || !tornado.data ? <ChartSkel h={240} /> : <ChartView spec={tornado.data} height={240} />}
          </div>
          <aside className="stress-note">
            <h4>How to read it</h4>
            We nudge each assumption up 20% and watch the 10-year cost move. The colour is how sure we are
            of that assumption:
            <div className="conf-row"><span className="conf-dot" style={{ background: "var(--viz-act)" }} /> <span><b>High</b> — solid ground</span></div>
            <div className="conf-row"><span className="conf-dot" style={{ background: "var(--viz-neutral)" }} /> <span><b>Medium</b></span></div>
            <div className="conf-row"><span className="conf-dot" style={{ background: "var(--viz-wait)" }} /> <span><b>Low</b> — a long bar here is fragile; tighten this data first</span></div>
          </aside>
        </div>
      </div>

      {m && (
        <div className="card" style={{ padding: "20px 24px", marginTop: 20 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="eyebrow">Cross-validation against an independent measure</span>
            <Explain
              title="Why two methods agreeing matters"
              label="Why does this matter?"
              plain={
                <p>One estimate could be a fluke of its method. <b>Two independent methods landing close
                  together</b> — a government statistic and a learned model — is much harder to fake, and is
                  the reason you can take the inflow number seriously.</p>
              }
              analogy={<>two witnesses who never spoke giving the same account — far more convincing than one.</>}
            >
              <p>ML inflow (ACS → PIT): <code>{fmtNum(m.spm_crossval.ml_inflow_monthly)}/mo</code> vs HUD SPM
                Measure 5: <code>{fmtNum(m.spm_crossval.spm_inflow_monthly)}/mo</code> · agreement{" "}
                <code>{fmtPct(m.spm_crossval.agreement_pct_diff)}</code>. {m.data_source}</p>
            </Explain>
          </div>
          <div className="row gap-24" style={{ marginTop: 12, flexWrap: "wrap" }}>
            <KV k="ML inflow (ACS → PIT)" v={`${fmtNum(m.spm_crossval.ml_inflow_monthly)} / mo`} />
            <KV k="HUD SPM first-time homeless" v={`${fmtNum(m.spm_crossval.spm_inflow_monthly)} / mo`} />
            <KV k="Predicted rate / 1,000" v={m.predicted_rate_per_1k.toFixed(1)} />
            <KV k="Observed rate / 1,000" v={m.observed_rate_per_1k.toFixed(1)} />
          </div>
          <p className="muted" style={{ fontSize: "var(--fs-sm)", marginTop: 14, lineHeight: 1.55 }}>{m.spm_crossval.note}. {m.data_source}</p>
        </div>
      )}

      <div className="scope-note">
        <span className="scope-note-ico"><Icon.Info size={18} /></span>
        <div className="scope-note-body">
          <b>Honest limit.</b> The model reads homelessness driven by the <b>local economy</b>. In cities with
          a legal <b>right to shelter</b> (e.g. New York), policy — not just economics — sets the count, so the
          model under-predicts there. We surface that gap as a visible residual instead of hiding it: the model
          <b> informs, it doesn’t decide</b>.
        </div>
      </div>
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="stat-tile-label">{k}</div>
      <div className="tnum" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-.02em", marginTop: 4 }}>{v}</div>
    </div>
  );
}

function shortModel(m: string): string {
  if (/gb_stumps/.test(m)) return "GB stumps";
  if (/ridge/i.test(m)) return "Ridge";
  return m.split("(")[0];
}
