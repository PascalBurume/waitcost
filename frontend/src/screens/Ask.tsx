import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { AskResult, ChartSpec, ToolsPayload, TrajectoryStep } from "../api/types";
import { useApp, useCityName } from "../state";
import { Icon } from "../lib/icons";
import { mdInline } from "../lib/format";
import { Modal, TierBadge, Provenance } from "../components/ui";
import { ChartView } from "../charts/ChartView";

const SUGGESTED = [
  "What does it cost to wait 3 years on a $15M program?",
  "What's the homelessness situation here?",
  "What is this city's plan?",
  "How long can we afford to wait before acting?",
  "Who bears homelessness most in this city?",
  "Is $15M or $50M the better annual budget?",
  "Recommend how to split a $30M budget",
];

// Tier-2 is a BINDING allocation recommendation. We gate those client-side: the
// backend has no needs-approval flag, so we withhold the answer behind the
// approval modal and only then POST with approve_allocation:true.
const ALLOCATION_RE = /\b(recommend|allocat|exact(ly)?\s+(split|divide|allocat)|binding|how (much|should).*(split|divide|allocat)|divide the budget|split the (budget|money|funds))\b/i;
function isAllocationAsk(q: string): boolean {
  return /allocat|\bsplit\b|\bdivide\b|\bbinding\b/i.test(q) && ALLOCATION_RE.test(q);
}

// Friendly label for an engine skill in the trajectory.
const STEP_LABEL: Record<string, string> = {
  fetch_hud_data: "Load HUD PIT + ACS data",
  check_data_support: "Check the data can support an answer",
  load_inflow_model: "Load the learned inflow model",
  route_city_brief: "Hand off to the City Brief agent",
  load_city_sources: "Load the cited source registry",
  retrieve_us_context: "Retrieve the city's indicators",
  equity_analysis: "Population-level equity analysis",
  run_simulation: "Run a Monte-Carlo scenario",
  compare_scenarios: "Compare act-now vs wait vs nothing",
  sensitivity_report: "Rank the assumptions that move the result",
  run_backtest: "Backtest the model against observed 2024",
  effect_sensitivity: "Stress the headline under ±50% effects",
  compare_budgets: "Compare candidate budgets",
  compare_mix: "Compare intervention mixes",
  regional_cost_of_waiting: "Rank the cost of waiting across cities",
  synthesize_decision: "Synthesize the recommendation",
  optimize_allocation: "Recommend a specific allocation",
  write_brief: "Write the decision brief",
};

// Friendly label for the question type (the answer eyebrow).
const INTENT_LABEL: Record<string, string> = {
  cost_of_waiting: "Cost of waiting",
  break_even: "Break-even timing",
  savings_now: "Savings from acting now",
  outcome_at_horizon: "Outcome at the horizon",
  compare_budgets: "Budget comparison",
  compare_mix: "Intervention-mix comparison",
  sensitivity: "Sensitivity / what drives it",
  roi: "Return on investment",
  cost_per_person: "Cost per person helped",
  regional: "Regional cost-of-inaction ranking",
  uncertainty: "How confident the number is",
  city_context: "City context",
  equity: "Equity / disparities",
  city_situation: "City situation · grounded brief",
  care_plan: "City care plan · grounded brief",
};

type Phase = "idle" | "thinking" | "answered" | "declined";

export function AskScreen({ tools }: { tools: ToolsPayload | null }) {
  const { coc } = useApp();
  const cityName = useCityName(coc);
  const [q, setQ] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [submitted, setSubmitted] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [revealed, setRevealed] = useState(0); // trajectory steps shown so far
  const [error, setError] = useState<Error | null>(null);
  const [chart, setChart] = useState<ChartSpec | null>(null);
  const [briefOpen, setBriefOpen] = useState(false);

  // Tier-2 gate
  const [gateOpen, setGateOpen] = useState(false);
  const [gateChecked, setGateChecked] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [gateRefused, setGateRefused] = useState(false);

  const timers = useRef<number[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  // re-running on city change clears the conversation
  useEffect(() => { reset(); /* eslint-disable-next-line */ }, [coc]);

  function reset() {
    timers.current.forEach(clearTimeout); timers.current = [];
    setPhase("idle"); setResult(null); setChart(null); setError(null);
    setRevealed(0); setBriefOpen(false); setApproved(false); setGateRefused(false);
  }

  async function run(question: string, approve_allocation: boolean) {
    setSubmitted(question);
    setPhase("thinking"); setResult(null); setChart(null); setError(null); setRevealed(0); setGateRefused(false);
    try {
      const res = await api.ask({ question, coc, approve_allocation });
      setResult(res);
      if (res.declined) {
        timers.current.push(window.setTimeout(() => setPhase("declined"), 650));
        return;
      }
      setApproved(approve_allocation);
      // progressively reveal the trajectory ("thinking stream"), then the answer
      const steps = res.trajectory ?? [];
      steps.forEach((_, i) => {
        timers.current.push(window.setTimeout(() => setRevealed(i + 1), 220 * (i + 1)));
      });
      timers.current.push(window.setTimeout(() => setPhase("answered"), 220 * (steps.length + 1) + 150));
      if (res.recommended_chart) {
        // For a budget sweep the chart must use the ACTUAL budgets asked about
        // (else cost_of_waiting_by_budget falls back to its default [1,15]).
        const sweepBudgets = res.sweep?.rows?.length
          ? res.sweep.rows.map((r) => r.budget_musd).join(",")
          : undefined;
        const chartDelay = res.sweep?.delay_years ?? res.plan?.delay_years ?? 3;
        api.chart(res.recommended_chart, coc, res.plan?.budget_musd ?? 50, chartDelay, undefined, sweepBudgets)
          .then(setChart).catch(() => setChart(null));
      }
    } catch (e) {
      setError(e as Error); setPhase("idle");
    }
  }

  function submit(question: string) {
    const text = question.trim();
    if (!text) return;
    if (isAllocationAsk(text)) {
      setPending(text); setGateChecked(false); setGateOpen(true);
      return;
    }
    run(text, false);
  }

  const facts = useMemo(() => {
    const cities = 17, agents = tools?.agents ?? 3, charts = tools?.charts ?? 15;
    return [
      { n: cities, t: "CoC cities" },
      { n: agents, t: "AI agents" },
      { n: charts, t: "decision charts" },
      { n: null, t: "runs fully offline" },
    ];
  }, [tools]);

  return (
    <div className="page">
      {phase === "idle" && !error && (
        <Hero q={q} setQ={setQ} onSubmit={submit} facts={facts} city={cityName} />
      )}
      {error && <Hero q={q} setQ={setQ} onSubmit={submit} facts={facts} city={cityName} error={error} />}

      {phase !== "idle" && (
        <div className="ask-result">
          <div className="ask-query-bar">
            <span className="agent-glow"><Icon.Search size={15} /></span>
            <span className="ask-query-text serif">{submitted}</span>
            <button className="btn btn-quiet btn-sm" onClick={reset}>New question</button>
          </div>

          {(phase === "thinking" || (phase === "answered" && result && !result.declined)) && result && (
            <ThinkingStream steps={result.trajectory ?? []} revealed={phase === "answered" ? (result.trajectory?.length ?? 0) : revealed} done={phase === "answered"} />
          )}
          {phase === "thinking" && !result && <ThinkingStream steps={[]} revealed={0} done={false} planning />}

          {phase === "declined" && result && <Declined result={result} onPick={(s) => { setQ(s); submit(s); }} />}

          {phase === "answered" && result && !result.declined && (
            <Answer result={result} chart={chart} approved={approved} briefOpen={briefOpen} setBriefOpen={setBriefOpen} city={cityName} />
          )}
          {gateRefused && <GateRefused onReset={reset} />}
        </div>
      )}

      <Modal open={gateOpen} onClose={() => setGateOpen(false)} labelledBy="gate-title">
        <div className="approval-modal">
          <div className="approval-head">
            <TierBadge tier={2} />
            <div className="approval-title" id="gate-title" style={{ marginTop: 10 }}>This is a Tier-2 action: recommending a specific allocation</div>
          </div>
          <p className="approval-body">
            WaitCost can <b>inform</b> a budget split, but a binding allocation recommendation requires a
            named human to sign off. The tool informs — it does not execute or decide.
          </p>
          <div className="approval-detail">
            <div className="serif" style={{ color: "var(--ink)" }}>{pending}</div>
          </div>
          <label className="approval-check">
            <input type="checkbox" checked={gateChecked} onChange={(e) => setGateChecked(e.target.checked)} />
            <span>I am the budget director (or their delegate). I understand this output <b>informs, and does not execute,</b> an allocation decision, and I take responsibility for the call.</span>
          </label>
          <div className="approval-actions">
            <button className="btn btn-ghost btn-sm" onClick={() => { setGateOpen(false); setGateRefused(true); setPhase("idle"); }}>Skip</button>
            <button className="btn btn-primary btn-sm" disabled={!gateChecked}
              onClick={() => { setGateOpen(false); if (pending) run(pending, true); }}>
              <Icon.Check size={15} /> Approve &amp; continue
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function Hero({ q, setQ, onSubmit, facts, city, error }: {
  q: string; setQ: (s: string) => void; onSubmit: (s: string) => void;
  facts: { n: number | null; t: string }[]; city: string; error?: Error;
}) {
  return (
    <div className="ask-hero">
      <span className="eyebrow">WaitCost · {city}</span>
      <h1 className="ask-h1 serif">What does delay cost?</h1>
      <p className="lede" style={{ marginTop: 14 }}>
        Ask in plain English. WaitCost runs the real engine — government data, honest uncertainty, and
        an AI that shows its work. A human, not the AI, makes the final allocation call.
      </p>
      <form className="ask-input" onSubmit={(e) => { e.preventDefault(); onSubmit(q); }}>
        <span className="ask-input-ico"><Icon.Search size={20} /></span>
        <input value={q} onChange={(e) => setQ(e.target.value)} aria-label="Ask a budget-timing question"
          placeholder={`Ask about ${city}…`} autoFocus />
        <button className="btn btn-primary btn-sm" type="submit" aria-label="Ask"><Icon.Send size={16} /></button>
      </form>
      {error && (
        <p style={{ color: "var(--viz-wait-2)", marginTop: 14, fontSize: "var(--fs-sm)", fontWeight: 600 }}>
          The engine isn't responding — start it with “uvicorn api.main:app --reload --port 8000”.
        </p>
      )}
      <div className="suggested">
        {SUGGESTED.map((s) => (
          <button key={s} className="suggest-chip" onClick={() => { setQ(s); onSubmit(s); }}>
            <Icon.ChevronRight size={13} />{s}
          </button>
        ))}
      </div>
      <div className="ask-facts">
        {facts.map((f, i) => (
          <span key={i} style={{ whiteSpace: "nowrap" }}>
            {f.n != null && <b>{f.n} </b>}{f.t}{i < facts.length - 1 && <span className="sep"> · </span>}
          </span>
        ))}
      </div>
    </div>
  );
}

function ThinkingStream({ steps, revealed, done, planning }: {
  steps: TrajectoryStep[]; revealed: number; done: boolean; planning?: boolean;
}) {
  return (
    <div className="card thinking-card">
      <div className="thinking-head">
        <div className="row gap-10">
          <span className="agent-glow">{done ? <Icon.Check size={15} /> : <span className="spin"><Icon.Spinner size={15} /></span>}</span>
          <b style={{ fontSize: "var(--fs-base)" }}>{done ? "Reasoning complete" : "Running the engine…"}</b>
        </div>
        <span className="pill">{steps.length || "…"} steps · {steps.filter((s) => s.tier >= 1).length || "…"} analysis calls</span>
      </div>
      {planning && <div className="step-detail">Planning the right computation…</div>}
      <div className="steps">
        {steps.slice(0, revealed).map((s, i) => {
          const running = !done && i === revealed - 1;
          const status = running ? "running" : "done";
          return (
            <div className="step-item fade" key={i} data-status="done">
              <div className="step-rail"><span className={`step-dot ${status}`}>{status === "done" ? <Icon.Check size={12} /> : <span className="spin"><Icon.Spinner size={12} /></span>}</span></div>
              <div className="step-body">
                <div className="step-head">
                  <span className="step-label">{STEP_LABEL[s.skill] ?? s.skill}</span>
                  {s.detail && <span className="step-detail-inline">· {s.detail}</span>}
                  <span className="step-tool">{s.skill}</span>
                  <TierBadge tier={s.tier} compact />
                  {s.tier === 2 && s.approved && <span className="pill" style={{ color: "var(--accent-ink)" }}>approved</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Pull the headline figure + 80% range out of the API's markdown sentence. */
function parseHeadline(direct: string): { num: string | null; range: string | null } {
  const numMatch = direct.match(/\$[\d,]+(?:\.\d+)?\s?[MB]?/);
  const rangeMatch = direct.match(/range\s*(\$[\d,.]+\s?[MB]?\s*[–-]\s*\$[\d,.]+\s?[MB]?)/i);
  return { num: numMatch ? numMatch[0].trim() : null, range: rangeMatch ? rangeMatch[1].trim() : null };
}

function Answer({ result, chart, approved, briefOpen, setBriefOpen, city }: {
  result: AskResult; chart: ChartSpec | null; approved: boolean;
  briefOpen: boolean; setBriefOpen: (b: boolean) => void; city: string;
}) {
  const direct = result.direct_answer ?? "";
  const { num, range } = parseHeadline(direct);
  const isBrief = !!result.city_brief || !!result.label;
  // A budget sweep states cost-of-waiting PER budget, so parseHeadline would grab a
  // budget LABEL ("$1M") as the hero number. Render the per-budget rows instead.
  const sweepRows = (result.sweep?.rows ?? []).filter((r) => r.cost_of_waiting);
  const isSweep = sweepRows.length > 0;
  return (
    <div className="answer-stack rise">
      <div className="card answer-card">
        <div className="answer-eyebrow">
          <span className="eyebrow">{isBrief ? "City brief" : "Direct answer"}</span>
          <span className="pill">{INTENT_LABEL[result.intent ?? ""] ?? (result.intent ?? "").replace(/_/g, " ")}</span>
          {isBrief && (
            <span className="pill" title="Qualitative context from cited sources — not the calibrated cost simulator." style={{ marginLeft: "auto" }}>
              {result.online ? "● live" : "○ offline"} · general context
            </span>
          )}
        </div>
        {isBrief && (
          <div className="brief-label-note" style={{ fontSize: "var(--fs-sm)", color: "var(--ink-2)", marginBottom: 8 }}>
            {result.label ?? "General context — not the calibrated cost model."}
          </div>
        )}
        {isSweep && !isBrief && (
          <Provenance metric="cost_of_waiting" label="Cost of waiting">
            <table className="sweep-table" style={{ width: "100%", borderCollapse: "collapse", margin: "4px 0 8px", fontSize: "var(--fs-sm)" }}>
              <thead><tr>
                <th style={{ textAlign: "left", padding: "7px 8px", borderBottom: "2px solid var(--ink)", color: "var(--ink-2)", fontWeight: 700 }}>Program size</th>
                <th style={{ textAlign: "right", padding: "7px 8px", borderBottom: "2px solid var(--ink)", color: "var(--ink-2)", fontWeight: 700 }}>Cost of waiting</th>
                <th style={{ textAlign: "right", padding: "7px 8px", borderBottom: "2px solid var(--ink)", color: "var(--ink-2)", fontWeight: 700 }}>80% range</th>
              </tr></thead>
              <tbody>{sweepRows.map((r, i) => {
                const cow = r.cost_of_waiting!;
                return (
                  <tr key={i}>
                    <td style={{ textAlign: "left", padding: "7px 8px", borderBottom: "1px solid var(--hairline)", fontWeight: 600 }}>${r.budget_musd.toLocaleString()}M/yr</td>
                    <td className="tnum" style={{ textAlign: "right", padding: "7px 8px", borderBottom: "1px solid var(--hairline)", color: "var(--accent-ink)", fontWeight: 700 }}>{fmtMB(cow.extra_cost_median / 1e6)}</td>
                    <td className="tnum" style={{ textAlign: "right", padding: "7px 8px", borderBottom: "1px solid var(--hairline)", color: "var(--ink-2)" }}>{fmtMB(cow.extra_cost_p10 / 1e6)} – {fmtMB(cow.extra_cost_p90 / 1e6)}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          </Provenance>
        )}
        {num && !isBrief && !isSweep && (
          <div className="answer-headline">
            <Provenance metric="cost_of_waiting" label="Cost of waiting">
              <span className="answer-num tnum">{num}</span>
            </Provenance>
            {range && <span className="answer-range tnum">80% range {range}</span>}
          </div>
        )}
        <p className="answer-sentence" dangerouslySetInnerHTML={{ __html: mdInline(direct) }} />
        {approved && (
          <div className="approved-note"><Icon.Check size={15} /> Tier-2 allocation step ran with your recorded approval.</div>
        )}
      </div>

      {result.decision && <Recommendation decision={result.decision} />}

      {result.decision && result.brief_markdown && !briefOpen && (
        <button
          type="button"
          className="evidence-jump"
          onClick={() => {
            setBriefOpen(true);
            document.getElementById("decision-brief")?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
          style={{
            alignSelf: "center", background: "none", border: "none", cursor: "pointer",
            color: "var(--ink-2)", font: "inherit", fontSize: "var(--fs-sm)",
            textDecoration: "underline", textUnderlineOffset: 3, padding: "2px 8px",
          }}
        >
          See the full evidence &amp; sources ↓
        </button>
      )}

      {chart && (
        <div className="card chart-card">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
            <span className="chart-title">{chart.title}</span>
            <span className="pill">recommended chart</span>
          </div>
          {chart.subtitle && <div className="chart-cap" style={{ marginTop: 0, marginBottom: 8 }}>{chart.subtitle}</div>}
          <ChartView spec={chart} />
        </div>
      )}

      <Trajectory steps={result.trajectory ?? []} />

      {result.brief_markdown && (
        <div className="card brief-card" id="decision-brief">
          <button className="brief-toggle" aria-expanded={briefOpen} onClick={() => setBriefOpen(!briefOpen)}>
            <span className="row gap-10"><Icon.Doc size={17} /><b>Decision brief — the evidence</b><span className="muted" style={{ fontWeight: 400 }}>policy memo · sources &amp; ranges</span></span>
            <Icon.Chevron size={16} style={{ transform: briefOpen ? "rotate(180deg)" : "none", transition: "transform .2s" }} />
          </button>
          {briefOpen && <Brief markdown={result.brief_markdown} city={city} />}
        </div>
      )}
    </div>
  );
}

function fmtMB(m: number | null | undefined): string {
  if (m == null) return "—";
  const neg = m < 0, a = Math.abs(m);
  const s = a >= 1000 ? `$${(a / 1000).toFixed(1)}B` : `$${a.toFixed(1)}M`;
  return neg ? `−${s}` : s;
}

const VERDICT_ICON: Record<string, JSX.Element> = {
  act_now: <Icon.Check size={18} />,
  lean_act_now: <Icon.Scale size={18} />,
  can_wait: <Icon.Info size={18} />,
  review: <Icon.Info size={18} />,
};

function Recommendation({ decision }: { decision: NonNullable<AskResult["decision"]> }) {
  const v = decision.verdict;
  const conf = decision.direction_confidence;
  const ev = decision.evidence;
  // Only the bullets (the headline is shown in the verdict header).
  const bullets = decision.plain_summary
    .split("\n").map((l) => l.trim()).filter((l) => l.startsWith("- ")).map((l) => l.slice(2));

  return (
    <div className={`card decision-card v-${v}`}>
      <div className="decision-head">
        <span className="eyebrow">The recommendation · plain English</span>
        <ConfidenceMeter level={conf} />
      </div>

      <div className="decision-verdict">
        <span className={`verdict-ico v-${v}`}>{VERDICT_ICON[v] ?? <Icon.Info size={18} />}</span>
        <div>
          <div className="verdict-title">{decision.verdict_label}</div>
          <div className="verdict-sub">{decision.headline}</div>
        </div>
      </div>

      {ev.baseline_10yr_musd != null && ev.cost_of_waiting_musd != null && (
        <SliceBar baseline={ev.baseline_10yr_musd} slice={ev.cost_of_waiting_musd}
          range={ev.cost_of_waiting_range_musd} delay={ev.delay_years} />
      )}

      <div className="decision-chips">
        <DecChip label={`Cost of waiting ${ev.delay_years}y`} value={fmtMB(ev.cost_of_waiting_musd)}
          sub={ev.cost_of_waiting_range_musd ? `${fmtMB(ev.cost_of_waiting_range_musd[0])} – ${fmtMB(ev.cost_of_waiting_range_musd[1])}` : undefined} accent="wait" />
        {ev.savings_now_musd != null && (
          <DecChip label="Acting now saves" value={fmtMB(ev.savings_now_musd)} sub="vs. doing nothing" accent="act" />
        )}
        {ev.break_even_year != null && (
          <DecChip label="Decide before" value={`Year ${ev.break_even_year}`} sub="delay wastes a year of budget" />
        )}
      </div>

      {bullets.length > 0 && (
        <ul className="decision-bullets">
          {bullets.map((b, i) => <li key={i} dangerouslySetInnerHTML={{ __html: mdInline(b) }} />)}
        </ul>
      )}

      <div className="decision-foot muted">{decision.magnitude_note}</div>
    </div>
  );
}

function ConfidenceMeter({ level }: { level: "high" | "medium" | "low" }) {
  const filled = level === "high" ? 3 : level === "medium" ? 2 : 1;
  return (
    <span className={`conf-meter c-${level}`} title="How sure we are of the DIRECTION (act now vs wait) — separate from the exact dollar amount.">
      <span className="conf-dots">{[0, 1, 2].map((i) => <span key={i} className={`conf-pip${i < filled ? " on" : ""}`} />)}</span>
      <span className="conf-text">direction confidence: <b>{level}</b></span>
    </span>
  );
}

function SliceBar({ baseline, slice, range, delay }: {
  baseline: number; slice: number; range: [number, number] | null; delay: number;
}) {
  const pct = Math.max(0, Math.min(100, (slice / baseline) * 100));
  const drawPct = Math.max(pct, 1.2);             // keep the sliver visible
  const hiPct = range ? Math.max(0, Math.min(100, (range[1] / baseline) * 100)) : pct;
  return (
    <div className="slice-viz">
      <div className="slice-row">
        <span className="slice-tag">Total 10-yr cost</span>
        <span className="slice-track"><span className="slice-fill base" /></span>
        <span className="slice-val">{fmtMB(baseline)}</span>
      </div>
      <div className="slice-row">
        <span className="slice-tag">Your decision moves</span>
        <span className="slice-track">
          <span className="slice-fill range" style={{ width: `${Math.max(hiPct, drawPct)}%` }} />
          <span className="slice-fill lever" style={{ width: `${drawPct}%` }} />
        </span>
        <span className="slice-val accent">{fmtMB(slice)}</span>
      </div>
      <div className="slice-caption">
        Most of the <b>{fmtMB(baseline)}</b> is unavoidable no matter what you do. Your timing decision moves
        only the highlighted sliver — about <b>{fmtMB(slice)}</b> (≈{pct < 1 ? "<1" : pct.toFixed(0)}% of the
        total). <b>That slice is the number to watch.</b>
      </div>
    </div>
  );
}

function DecChip({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: "act" | "wait" }) {
  return (
    <div className={`dec-chip${accent ? ` a-${accent}` : ""}`}>
      <div className="dec-chip-label">{label}</div>
      <div className="dec-chip-val tnum">{value}</div>
      {sub && <div className="dec-chip-sub">{sub}</div>}
    </div>
  );
}

function Trajectory({ steps }: { steps: TrajectoryStep[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="card brief-card">
      <button className="brief-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="row gap-10"><Icon.Shield size={17} /><b>Agent trajectory</b><span className="muted" style={{ fontWeight: 400 }}>{steps.length} tool calls · action tiers logged</span></span>
        <Icon.Chevron size={16} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }} />
      </button>
      {open && (
        <div className="brief-body" style={{ paddingTop: 16 }}>
          <div className="steps">
            {steps.map((s, i) => (
              <div className="step-item" key={i} data-status="done">
                <div className="step-rail"><span className="step-dot done"><Icon.Check size={12} /></span></div>
                <div className="step-body"><div className="step-head">
                  <span className="step-label">{STEP_LABEL[s.skill] ?? s.skill}</span>
                  {s.detail && <span className="step-detail-inline">· {s.detail}</span>}
                  <span className="step-tool">{s.skill}</span>
                  <TierBadge tier={s.tier} compact />
                  {s.tier === 2 && s.approved && <span className="pill">approved by human</span>}
                </div></div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Brief({ markdown, city }: { markdown: string; city: string }) {
  // Render the API's markdown brief faithfully (headings, tables, blockquotes,
  // bold) in the serif "policy memo" voice — no numbers are invented here.
  const blocks = parseMd(markdown);
  return (
    <div className="brief-body">
      <div className="brief-memo-head">
        <div>
          <div className="brief-to">Decision brief · {city}</div>
          <div className="brief-title serif">WaitCost — cost-of-delay analysis</div>
        </div>
        <div className="brief-meta">Population-level · Informs, does not decide<br />All figures are ranges</div>
      </div>
      {blocks}
    </div>
  );
}

// Minimal, safe markdown → React (headings, tables, blockquote, lists, bold).
function parseMd(md: string): JSX.Element[] {
  const lines = md.split("\n");
  const out: JSX.Element[] = [];
  let i = 0, key = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.startsWith("# ")) { i++; continue; } // memo head replaces the H1
    if (/^#{2,} /.test(line)) {
      out.push(<h3 key={key++} className="serif" style={{ fontSize: "var(--fs-h3)", margin: "20px 0 8px" }}>{line.replace(/^#+ /, "")}</h3>);
      i++; continue;
    }
    if (line.startsWith(">")) {
      out.push(<p key={key++} style={{ borderLeft: "3px solid var(--accent)", paddingLeft: 14, color: "var(--ink-2)", fontStyle: "italic" }}
        dangerouslySetInnerHTML={{ __html: mdInline(line.replace(/^>\s?/, "")) }} />);
      i++; continue;
    }
    if (line.trim().startsWith("|")) {
      const rows: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) { rows.push(lines[i]); i++; }
      out.push(<MdTable key={key++} rows={rows} />);
      continue;
    }
    if (/^[-*] /.test(line.trim())) {
      const items: string[] = [];
      while (i < lines.length && /^[-*] /.test(lines[i].trim())) { items.push(lines[i].trim().replace(/^[-*] /, "")); i++; }
      out.push(<ul key={key++} style={{ paddingLeft: 18, margin: "4px 0 12px" }}>
        {items.map((it, j) => <li key={j} style={{ fontSize: "var(--fs-sm)", color: "var(--ink-2)", marginBottom: 4 }} dangerouslySetInnerHTML={{ __html: mdInline(it) }} />)}
      </ul>);
      continue;
    }
    out.push(<p key={key++} dangerouslySetInnerHTML={{ __html: mdInline(line) }} />);
    i++;
  }
  return out;
}

function MdTable({ rows }: { rows: string[] }) {
  const cells = rows.map((r) => r.split("|").slice(1, -1).map((c) => c.trim()));
  const body = cells.filter((r) => !r.every((c) => /^:?-+:?$/.test(c)));
  const [head, ...rest] = body;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", margin: "8px 0 16px", fontSize: "var(--fs-sm)" }}>
      <thead><tr>{head.map((c, j) => <th key={j} style={{ textAlign: j ? "right" : "left", padding: "7px 8px", borderBottom: "2px solid var(--ink)", color: "var(--ink-2)", fontWeight: 700 }} dangerouslySetInnerHTML={{ __html: mdInline(c) }} />)}</tr></thead>
      <tbody>{rest.map((r, ri) => <tr key={ri}>{r.map((c, j) => <td key={j} className={j ? "tnum" : ""} style={{ textAlign: j ? "right" : "left", padding: "7px 8px", borderBottom: "1px solid var(--hairline)", color: "var(--ink-2)" }} dangerouslySetInnerHTML={{ __html: mdInline(c) }} />)}</tr>)}</tbody>
    </table>
  );
}

function Declined({ result, onPick }: { result: AskResult; onPick: (s: string) => void }) {
  // A greeting / meta question gets a warm welcome, not a refusal.
  const greeting = !!result.greeting;
  return (
    <div className="declined-wrap rise">
      <div className={`card declined-card${greeting ? " greeting" : ""}`}>
        <span className="declined-ico">{greeting ? <Icon.Info size={26} /> : <Icon.Slash size={26} />}</span>
        <div className="declined-h serif">{greeting ? "Hi — here's what I can help with" : "I work at the city level"}</div>
        <p className="declined-body">{result.reason ?? "This tool answers CoC-level budget-timing questions — it doesn't profile individuals or sub-city geographies."}</p>
        <div className="declined-alt">{greeting ? "Try asking" : "Try an in-scope question"}</div>
        <div className="declined-suggest">
          {["What does it cost to wait 3 years?", "How long can we afford to wait?", "Who bears homelessness most here?"].map((s) => (
            <button key={s} className="suggest-chip" style={{ justifyContent: "center" }} onClick={() => onPick(s)}>{s}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

function GateRefused({ onReset }: { onReset: () => void }) {
  return (
    <div className="declined-wrap rise">
      <div className="card declined-card">
        <span className="declined-ico"><Icon.Lock size={24} /></span>
        <div className="declined-h serif">Allocation withheld</div>
        <p className="declined-body">A binding allocation recommendation is a Tier-2 action. Without a named human's sign-off, WaitCost won't produce it. You can still explore informational budget/mix comparisons.</p>
        <button className="btn btn-ghost btn-sm" style={{ marginTop: 18 }} onClick={onReset}>Ask something else</button>
      </div>
    </div>
  );
}
