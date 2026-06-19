import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { EffectBand, ScenarioPayload } from "../api/types";
import { useApp, useCityName } from "../state";
import { fmtMusd } from "../lib/format";
import { Axes, Legend, areaFrom, lin, niceMax, pathFrom, useTip } from "../charts/primitives";
import { CostDonut } from "../charts/CostDonut";
import { ChartSkel, ErrorState, StatTile } from "../components/ui";

interface Mix { prev: number; rrh: number; psh: number; }
const DEFAULT_MIX: Mix = { prev: 34, rrh: 33, psh: 33 };

export function ExploreScreen() {
  const { coc, params } = useApp();
  const city = useCityName(coc);
  const [budget, setBudget] = useState(15);
  const [delay, setDelay] = useState(3);
  const [mix, setMix] = useState<Mix>(DEFAULT_MIX);

  const [scn, setScn] = useState<ScenarioPayload | null>(null);
  const [eff, setEff] = useState<EffectBand | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const debounce = useRef<number | undefined>(undefined);

  // Debounced fetch on any control / city change.
  useEffect(() => {
    window.clearTimeout(debounce.current);
    setLoading(true);
    const ctrl = new AbortController();
    debounce.current = window.setTimeout(() => {
      const total = mix.prev + mix.rrh + mix.psh || 1;
      // Keys must match the engine's canonical intervention names (model/states.py).
      const mixFrac = {
        prevention: mix.prev / total,
        rapid_rehousing: mix.rrh / total,
        permanent_supportive_housing: mix.psh / total,
      };
      Promise.all([
        api.scenario({ budget_musd: budget, delay_years: delay, n_mc: 120, mix: mixFrac, coc }, ctrl.signal),
        api.effectBand(budget, delay, ctrl.signal),
      ]).then(([s, e]) => { setScn(s); setEff(e); setLoading(false); setError(null); })
        .catch((err) => { if (err?.name !== "AbortError") { setError(err); setLoading(false); } });
    }, 280);
    return () => { ctrl.abort(); window.clearTimeout(debounce.current); };
  }, [budget, delay, mix, coc]);

  const cow = scn?.cost_of_waiting_musd;
  const sq = scn?.scenarios.find((s) => /status quo/i.test(s.scenario));
  const now = scn?.scenarios.find((s) => /act now/i.test(s.scenario));
  const savings = sq && now ? sq.cum_cost_p50_musd - now.cum_cost_p50_musd : null;

  return (
    <div className="page page-wide">
      <div className="section-head">
        <span className="eyebrow">Explore · {city}</span>
        <h1 className="page-title serif">Tune the program, watch the cost of waiting</h1>
        <p className="lede">Every line and number is recomputed live by the engine. The y-axis fits the data, so the three paths and their 80% bands stay distinguishable.</p>
      </div>

      {error ? <ErrorState error={error} onRetry={() => setBudget((b) => b)} /> : (
        <div className="explore-grid">
          <div className="card explore-controls">
            <Slider label="Annual budget" value={budget} min={0} max={100} step={5} fmt={(v) => `$${v}M`} onChange={setBudget}
              sub="New annual spend on intervention." />
            <Slider label="Years of delay" value={delay} min={0} max={8} step={1} fmt={(v) => `${v} yr`} onChange={setDelay}
              sub="How long before the program starts." />
            <MixControl mix={mix} setMix={setMix} />
            <button className="btn btn-ghost btn-sm reset-btn" onClick={() => { setBudget(15); setDelay(3); setMix(DEFAULT_MIX); }}>
              Reset to baseline
            </button>
          </div>

          <div className="explore-main">
            <div className="kpi-row">
              <StatTile label={`COST OF WAITING ${delay} YR`} value={cow ? fmtMusd(cow.p50) : "—"} big accent="var(--viz-wait-2)"
                prov="cost_of_waiting"
                sub={cow ? `80% range ${fmtMusd(cow.p10)} – ${fmtMusd(cow.p90)}` : "computing…"} />
              <StatTile label="ACTING NOW SAVES VS NOTHING" value={savings != null ? fmtMusd(savings) : "—"}
                prov="scenario"
                sub={now ? `${Math.round(now.active_homeless).toLocaleString()} homeless at horizon` : "computing…"} accent="var(--accent-ink)" />
              <StatTile label="STATUS-QUO 10-YR COST" value={sq ? fmtMusd(sq.cum_cost_p50_musd) : "—"}
                prov="scenario"
                sub={sq ? `80% ${fmtMusd(sq.cum_cost_p10_musd)} – ${fmtMusd(sq.cum_cost_p90_musd)}` : "computing…"} />
            </div>

            <div className="card chart-card">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 2 }}>
                <span className="chart-title">Where your program's 10-year cost goes</span>
                <span className="pill">{loading ? "updating…" : "live"}</span>
              </div>
              <div className="chart-cap" style={{ marginTop: 0, marginBottom: 8 }}>The cost if you act now at this budget &amp; mix, by group — tune the sliders and watch the total drop (and the green savings grow) below the do-nothing baseline.</div>
              {scn ? <CostDonut composition={scn.composition} /> : <ChartSkel h={220} />}
              <div className="chart-src" style={{ marginTop: 10 }}><span aria-hidden>◆</span> Per-group public cost = people in each group × per-person monthly cost (Economic Roundtable) × time, discounted.</div>
            </div>

            <div className="card chart-card">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 2 }}>
                <span className="chart-title">What your decision is worth, over time</span>
                <span className="pill">{loading ? "updating…" : "live"}</span>
              </div>
              <div className="chart-cap" style={{ marginTop: 0, marginBottom: 8 }}>Extra public cost vs. acting now — the gap that opens above the baseline is the cost of waiting (and the do-nothing penalty), growing each year.</div>
              {scn ? <FanChart scn={scn} /> : <ChartSkel h={420} />}
              <div className="chart-src" style={{ marginTop: 10 }}><span aria-hidden>◆</span> Paired Monte-Carlo differences vs. the act-now baseline (HUD PIT + Census ACS). Shaded = 80% (P10–P90) range.</div>
            </div>

            <div className="card sens-strip">
              <span className="eyebrow">Sensitivity · headline under ±50% intervention effects</span>
              {eff ? <SensStrip eff={eff} /> : <ChartSkel h={80} />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Slider({ label, value, min, max, step, fmt, onChange, sub }: {
  label: string; value: number; min: number; max: number; step: number;
  fmt: (v: number) => string; onChange: (v: number) => void; sub?: string;
}) {
  return (
    <div className="slider-wrap">
      <div className="slider-row">
        <label className="slider-label" htmlFor={`sl-${label}`}>{label}</label>
        <span className="slider-val tnum">{fmt(value)}</span>
      </div>
      <input id={`sl-${label}`} type="range" min={min} max={max} step={step} value={value}
        aria-valuetext={fmt(value)} onChange={(e) => onChange(Number(e.target.value))} />
      {sub && <div className="slider-sub" style={{ marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function MixControl({ mix, setMix }: { mix: Mix; setMix: (m: Mix) => void }) {
  const total = mix.prev + mix.rrh + mix.psh || 1;
  const seg = [
    { k: "prev" as const, label: "Prevention", color: "var(--viz-neutral)" },
    { k: "rrh" as const, label: "Rapid re-housing", color: "var(--viz-act)" },
    { k: "psh" as const, label: "Supportive housing", color: "var(--viz-wait)" },
  ];
  return (
    <div className="mix-block">
      <div>
        <div className="slider-label" style={{ marginBottom: 8 }}>Intervention mix</div>
        <div className="mix-bar" aria-hidden>
          {seg.map((s) => <span key={s.k} style={{ width: `${(mix[s.k] / total) * 100}%`, background: s.color }} />)}
        </div>
      </div>
      {seg.map((s) => (
        <div key={s.k}>
          <div className="slider-row">
            <span className="slider-sub"><span style={{ display: "inline-block", width: 9, height: 9, borderRadius: 3, background: s.color, marginRight: 7 }} />{s.label}</span>
            <span className="slider-val tnum">{Math.round((mix[s.k] / total) * 100)}%</span>
          </div>
          <input type="range" min={0} max={100} step={1} value={mix[s.k]} aria-label={`${s.label} share`}
            onChange={(e) => setMix({ ...mix, [s.k]: Number(e.target.value) })} />
        </div>
      ))}
    </div>
  );
}

/** Divergence chart: extra public cost vs. acting now, by year. Acting now is the
 *  flat $0 baseline; the GAP that opens above it is the cost of waiting / the
 *  do-nothing penalty — visible here precisely because the absolute totals overlap. */
function FanChart({ scn }: { scn: ScenarioPayload }) {
  const { show, hide, node } = useTip();
  const W = 780, h = 430, pad = { l: 80, r: 132, t: 24, b: 44 };
  const dv = scn.divergence;
  if (!dv) return <ChartSkel h={h} />;
  const series = [
    { key: "delay", band: dv.delay, label: `Cost of waiting (delay ${scn.delay_years}y)`, color: "var(--viz-wait-2)", dash: "" },
    { key: "status_quo", band: dv.status_quo, label: "Do-nothing penalty", color: "var(--viz-neutral)", dash: "5 5" },
  ] as const;
  const xs = dv.years;
  const allLo = series.flatMap((s) => s.band.p10);
  const allHi = series.flatMap((s) => s.band.p90);
  const dmin = Math.min(0, ...allLo), dmax = Math.max(...allHi);
  const floor = dmin - (dmax - dmin) * 0.05;
  const ceil = niceMax(dmax + (dmax - dmin) * 0.06);
  const x = lin(Math.min(...xs), Math.max(...xs), pad.l, W - pad.r);
  const y = lin(floor, ceil, h - pad.b, pad.t);
  const yTicks = Array.from({ length: 5 }, (_, i) => floor + ((ceil - floor) / 4) * i);
  const y0 = y(0);

  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img"
        aria-label={`Extra public cost versus acting now, by year — the cost of waiting and the do-nothing penalty grow over ${xs[xs.length - 1]} years.`}>
        <Axes x={x} y={y} w={W} h={h} pad={pad} yTicks={yTicks} xTicks={xs}
          yFmt={fmtMusd} xFmt={(t) => `Y${t}`} xLabel="Years from today" yLabel="Extra cost vs. acting now" />
        {/* 80% bands (paired Monte-Carlo differences) */}
        {series.map((s) => (
          <path key={s.key + "b"} fill={s.color} opacity={0.15} stroke="none"
            d={areaFrom(xs.map((xv, j) => [x(xv), y(s.band.p90[j])]), xs.map((xv, j) => [x(xv), y(s.band.p10[j])]))} />
        ))}
        {/* acting-now baseline at $0 */}
        <line x1={pad.l} x2={W - pad.r} y1={y0} y2={y0} stroke="var(--viz-act)" strokeWidth="2.4" />
        {/* P50 divergence lines + per-year dots */}
        {series.map((s) => (
          <path key={s.key} fill="none" stroke={s.color} strokeWidth="2.8" strokeDasharray={s.dash}
            strokeLinecap="round" strokeLinejoin="round"
            d={pathFrom(xs.map((xv, j) => [x(xv), y(s.band.p50[j])]))} />
        ))}
        {series.flatMap((s) => xs.map((xv, j) => (
          <circle key={s.key + j} cx={x(xv)} cy={y(s.band.p50[j])} r="2.6"
            fill="var(--surface)" stroke={s.color} strokeWidth="1.6" />
        )))}
        {/* end-of-line labels in the right gutter, nudged apart so they never
            overlap — even when the cost-of-waiting line sits on the baseline (small
            delay). A thin leader connects each label to where its line actually ends. */}
        {(() => {
          const last = xs.length - 1;
          const items = [
            { key: "act", color: "var(--viz-act)", text: "Act now · $0", y0: y0 },
            ...series.map((s) => ({
              key: s.key, color: s.color, y0: y(s.band.p50[last]),
              text: `+${fmtMusd(s.band.p50[last])}`,
            })),
          ].map((it) => ({ ...it, ly: it.y0 })).sort((a, b) => a.y0 - b.y0);
          const GAP = 16;
          for (let i = 1; i < items.length; i++)
            if (items[i].ly < items[i - 1].ly + GAP) items[i].ly = items[i - 1].ly + GAP;
          const overflow = items.length ? items[items.length - 1].ly - (h - pad.b) : 0;
          if (overflow > 0) items.forEach((it) => (it.ly -= overflow));
          return items.map((it, i) => (
            <g key={i}>
              {it.key !== "act" && Math.abs(it.ly - it.y0) > 1 && (
                <line x1={W - pad.r + 1} x2={W - pad.r + 6} y1={it.y0} y2={it.ly}
                  stroke={it.color} strokeWidth="1" opacity="0.55" />
              )}
              <text x={W - pad.r + 9} y={it.ly} dominantBaseline="middle"
                fontSize="11.5" fontWeight="700" fill={it.color}>{it.text}</text>
            </g>
          ));
        })()}
        {/* hover columns */}
        {xs.map((xv, j) => (
          <rect key={xv} x={x(xv) - (W - pad.l - pad.r) / (xs.length * 2)} y={pad.t}
            width={(W - pad.l - pad.r) / xs.length} height={h - pad.t - pad.b} fill="transparent"
            onMouseMove={(e) => show(e, (
              <div>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>Year {xv}</div>
                {series.map((s) => <div key={s.key} className="tip-row"><span className="tip-k">{s.label}</span><span>+{fmtMusd(s.band.p50[j])}</span></div>)}
                <div className="tip-row"><span className="tip-k">Act now</span><span>$0 (baseline)</span></div>
              </div>
            ))} onMouseLeave={hide} />
        ))}
      </svg>
      <Legend items={[
        { label: `Cost of waiting (delay ${scn.delay_years}y)`, color: "var(--viz-wait-2)" },
        { label: "Do-nothing penalty", color: "var(--viz-neutral)", dashed: true },
        { label: "Act now (baseline)", color: "var(--viz-act)" },
        { label: "80% range", color: "var(--viz-band)", swatch: true },
      ]} />
      {node}
    </div>
  );
}

/** ±50% effect sensitivity strip: headline as a range. */
function SensStrip({ eff }: { eff: EffectBand }) {
  const lo = eff.cow_lo_musd, base = eff.cow_base_musd, hi = eff.cow_hi_musd;
  const span = hi - lo || 1;
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - lo) / span) * 100))}%`;
  return (
    <div>
      <div className="answer-headline" style={{ marginTop: 12 }}>
        <span className="stat-num tnum" style={{ fontSize: 34, color: "var(--viz-wait-2)" }}>{fmtMusd(base)}</span>
        <span className="answer-range tnum">under ±50% effects: {fmtMusd(lo)} – {fmtMusd(hi)}</span>
      </div>
      <div className="sens-track">
        <div className="sens-wide" style={{ left: 0, right: 0 }} />
        <div className="sens-fill" style={{ left: pos(lo), width: `calc(${pos(hi)} - ${pos(lo)})` }} />
        <div className="sens-marker" style={{ left: pos(base) }} />
        <div className="sens-flag" style={{ left: pos(base) }}>baseline {fmtMusd(base)}</div>
        <div className="sens-end left">{fmtMusd(lo)} · effects −50%</div>
        <div className="sens-end right">{fmtMusd(hi)} · effects +50%</div>
      </div>
      <p className="muted" style={{ fontSize: "var(--fs-sm)", marginTop: 6 }}>
        The <b>sign</b> is robust — waiting costs more across the whole band. The magnitude is a planning estimate that scales with the low-confidence intervention-effect priors.
      </p>
    </div>
  );
}
