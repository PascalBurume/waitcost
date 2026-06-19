// One renderer for every backend chart kind. Numbers come straight from the
// /chart spec; colors are remapped to the colorblind-safe design trio (the spec
// ships banned reds). Axes auto-fit the data (§6.2).
import type { ChartSpec, ChartSeries, CocPoint } from "../api/types";
import { Axes, Legend, areaFrom, lin, niceMax, pathFrom, useTip, vizColor } from "./primitives";
import { USMap } from "./USMap";
import { fmtMusd, fmtNum, fmtUsd } from "../lib/format";
import { Explain } from "../components/Explain";
import { Provenance } from "../components/ui";
import { Icon } from "../lib/icons";

const W = 760;

function nums(a?: (number | string | null)[]): number[] { return (a ?? []).map((v) => Number(v)); }
function fmtAxisMoney(t: number) { return t >= 1000 ? `$${(t / 1000).toFixed(1)}B` : `$${Math.round(t)}M`; }

/** A spec carries percentages when its y-axis label mentions "%". Bars/axes then
 *  read as rates (e.g. "87.8%"), not dollars — the engine reuses kind:"bar" for both. */
function isPercentSpec(spec: ChartSpec): boolean { return /%/.test(spec.y_label ?? "") || /%/.test(spec.series[0]?.name ?? ""); }

/** Greedy word-wrap a long category label into at most two lines (keeps "/" and
 *  spaces as break points) so axis labels never collide. Short labels pass through. */
function wrapLabel(label: string, maxChars: number): string[] {
  if (label.length <= maxChars) return [label];
  const parts = label.split(/(?<=[/\s])/);
  let l1 = "", l2 = "", wrapped = false;
  for (const w of parts) {
    // Once line 1 overflows, every remaining word goes to line 2 — never back to
    // line 1, or word order scrambles ("Hispanic/(any" + "Latino race)").
    if (!wrapped && (!l1 || (l1 + w).trim().length <= maxChars)) l1 += w;
    else { wrapped = true; l2 += w; }
  }
  l2 = l2.trim();
  if (!l2) return [l1.trim()];
  if (l2.length > maxChars) l2 = l2.slice(0, maxChars - 1) + "…";
  return [l1.trim(), l2];
}

export function ChartView({ spec, height = 380 }: { spec: ChartSpec; height?: number }) {
  const htr = spec.how_to_read;
  return (
    <div className="chart-frame">
      <Dispatch spec={spec} height={height} />
      {spec.caption && <div className="chart-cap">{spec.caption}</div>}
      {htr && (
        <div className="chart-howto">
          <Icon.Info size={14} />
          <span className="chart-howto-text"><b>How to read:</b> {htr.plain}</span>
          {(htr.analogy || htr.tech) && (
            <Explain title={spec.title} plain={htr.plain} analogy={htr.analogy} label="more">
              {htr.tech && <p>{htr.tech}</p>}
            </Explain>
          )}
        </div>
      )}
      {spec.source && (
        <div className="chart-src">
          <Provenance label="Chart data" entry={{ source: spec.source,
            note: "Engine output — figures are ranges, not point estimates." }}>
            <span aria-hidden>◆</span> {spec.source}
          </Provenance>
        </div>
      )}
    </div>
  );
}

function Dispatch({ spec, height }: { spec: ChartSpec; height: number }) {
  switch (spec.kind) {
    case "line_band": return <LineBand spec={spec} h={Math.max(height, 420)} />;
    case "line": return <LinePlot spec={spec} h={height} />;
    case "dot_interval": return <DotInterval spec={spec} h={Math.max(height, 300)} />;
    case "area": return <StackedArea spec={spec} h={height} />;
    case "bar_ci": return <BarCI spec={spec} h={height} />;
    case "waterfall": return <Waterfall spec={spec} h={height} />;
    case "bar": return spec.horizontal ? <HBar spec={spec} h={Math.max(height, 420)} /> : <VBar spec={spec} h={height} />;
    case "tornado": return <Tornado spec={spec} h={Math.max(height, 230)} />;
    case "shap_bar": return <ShapBar spec={spec} h={Math.max(height, 300)} />;
    case "scatter": return <Scatter spec={spec} h={Math.max(height, 420)} />;
    case "map": return <MapKind spec={spec} />;
    default: return <div className="muted">Unsupported chart kind: {spec.kind}</div>;
  }
}

/* ---------- line + bands (cost trajectory) ---------- */
function LineBand({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const pad = { l: 70, r: 70, t: 22, b: 44 };
  const xs = nums(spec.series[0].x);
  const allLo = spec.series.flatMap((s) => nums(s.y_lo ?? s.y));
  const allHi = spec.series.flatMap((s) => nums(s.y_hi ?? s.y));
  const dmin = Math.min(...allLo), dmaxRaw = Math.max(...allHi);
  // Anchor at 0: these are now divergence/counts charts where the zero line (act-now
  // reference, or an empty baseline) is the meaningful anchor — the gap above it is the story.
  const lo = Math.min(0, dmin);
  const hi = niceMax(dmaxRaw + (dmaxRaw - dmin) * 0.04);
  const x = lin(Math.min(...xs), Math.max(...xs), pad.l, W - pad.r);
  const y = lin(lo, hi, h - pad.b, pad.t);
  const yTicks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) / 4) * i);

  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        <Axes x={x} y={y} w={W} h={h} pad={pad} yTicks={yTicks} xTicks={xs}
          yFmt={fmtAxisMoney} xFmt={(t) => `Y${t}`} xLabel={spec.x_label} yLabel={spec.y_label} />
        {spec.series.map((s, i) => s.y_hi && s.y_lo ? (
          <path key={`b${i}`} fill={vizColor(s.name, i)} opacity={0.14} stroke="none"
            d={areaFrom(xs.map((xv, j) => [x(xv), y(Number(s.y_hi![j]))]),
                        xs.map((xv, j) => [x(xv), y(Number(s.y_lo![j]))]))} />
        ) : null)}
        {spec.series.map((s, i) => (
          <path key={`l${i}`} fill="none" stroke={vizColor(s.name, i)} strokeWidth={2.6}
            strokeDasharray={/delay|wait/i.test(s.name) ? "6 5" : ""} strokeLinecap="round" strokeLinejoin="round"
            d={pathFrom(xs.map((xv, j) => [x(xv), y(Number(s.y![j]))]))} />
        ))}
        {/* End-of-line value labels in the right gutter, nudged apart vertically so the
            three scenarios stay legible at Y{last} even where the lines visually overlap. */}
        {(() => {
          const last = xs.length - 1;
          const ends = spec.series.map((s, i) => ({
            color: vizColor(s.name, i), v: Number(s.y![last]),
            y0: y(Number(s.y![last])), ly: y(Number(s.y![last])),
          })).sort((a, b) => a.y0 - b.y0);
          const GAP = 15;
          for (let i = 1; i < ends.length; i++) if (ends[i].ly < ends[i - 1].ly + GAP) ends[i].ly = ends[i - 1].ly + GAP;
          const overflow = ends.length ? ends[ends.length - 1].ly - (h - pad.b) : 0;
          if (overflow > 0) ends.forEach((e) => (e.ly -= overflow));
          return ends.map((e, i) => (
            <g key={i}>
              <circle cx={W - pad.r} cy={e.y0} r={3} fill={e.color} />
              <line x1={W - pad.r + 3} x2={W - pad.r + 8} y1={e.y0} y2={e.ly} stroke={e.color} strokeWidth="1" opacity="0.6" />
              <text x={W - pad.r + 11} y={e.ly} dominantBaseline="middle" fontSize="11.5" fontWeight="700"
                fill={e.color} style={{ fontVariantNumeric: "tabular-nums" }}>{fmtMusd(e.v)}</text>
            </g>
          ));
        })()}
        {xs.map((xv) => {
          const j = xs.indexOf(xv);
          return (
            <rect key={xv} x={x(xv) - (W - pad.l - pad.r) / (xs.length * 2)} y={pad.t}
              width={(W - pad.l - pad.r) / xs.length} height={h - pad.t - pad.b} fill="transparent"
              onMouseMove={(e) => show(e, (
                <div>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>Year {xv}</div>
                  {spec.series.map((s, i) => (
                    <div key={i} className="tip-row"><span className="tip-k">{s.name}</span><span>{fmtMusd(Number(s.y![j]))}</span></div>
                  ))}
                </div>
              ))} onMouseLeave={hide} />
          );
        })}
      </svg>
      <Legend items={spec.series.map((s, i) => ({ label: s.name, color: vizColor(s.name, i), dashed: /delay|wait/i.test(s.name) }))} />
      {node}
    </>
  );
}

/* ---------- single line + annotations (break-even) ---------- */
function LinePlot({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const pad = { l: 64, r: 86, t: 22, b: 44 };
  const s = spec.series[0];
  const xs = nums(s.x), ys = nums(s.y);
  const annos = spec.annotations ?? [];
  const hline = annos.find((a: any) => a.type === "hline");
  const vmark = annos.find((a: any) => a.type === "vmarker");
  const annual = hline ? Number(hline.y) : 0;
  // Raise the y-max so the threshold line is on-canvas — the whole point of the chart.
  const hi = niceMax(Math.max(...ys, annual) * 1.08);
  const x = lin(Math.min(...xs), Math.max(...xs), pad.l, W - pad.r);
  const y = lin(0, hi, h - pad.b, pad.t);
  const yTicks = Array.from({ length: 5 }, (_, i) => (hi / 4) * i);
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        <Axes x={x} y={y} w={W} h={h} pad={pad} yTicks={yTicks} xTicks={xs}
          yFmt={fmtAxisMoney} xFmt={(t) => `Y${t}`} xLabel={spec.x_label} yLabel={spec.y_label} />
        {/* "waiting stops paying off" zone above the threshold */}
        {hline && <rect x={pad.l} y={pad.t} width={W - pad.l - pad.r}
          height={Math.max(0, y(annual) - pad.t)} fill="var(--viz-wait)" opacity={0.06} />}
        <path d={areaFrom(xs.map((xv, j) => [x(xv), y(ys[j])]), xs.map((xv) => [x(xv), y(0)]))}
          fill="var(--viz-wait)" opacity={0.13} />
        <path d={pathFrom(xs.map((xv, j) => [x(xv), y(ys[j])]))} fill="none" stroke="var(--viz-wait)" strokeWidth="2.8" strokeLinecap="round" />
        {xs.map((xv, j) => {
          const past = ys[j] > annual && annual > 0;
          return (
            <g key={xv} onMouseMove={(e) => show(e, (
              <div>
                <b>Wait {xv} {xv === 1 ? "year" : "years"}</b>
                <div className="tip-row"><span className="tip-k">extra cost vs acting now</span><span>{fmtMusd(ys[j])}</span></div>
                {annual > 0 && <div className="tip-row"><span className="tip-k">one year of budget</span><span>{fmtMusd(annual)}</span></div>}
                <div className="tip-row"><span className="tip-k">{past ? "⚠ past break-even" : "still pays off"}</span>
                  <span>{past ? "waiting costs more than a year of budget" : "below the threshold"}</span></div>
              </div>))} onMouseLeave={hide} style={{ cursor: "pointer" }}>
              <circle cx={x(xv)} cy={y(ys[j])} r="13" fill="transparent" />
              <circle cx={x(xv)} cy={y(ys[j])} r={past ? 4 : 3} fill="var(--surface)"
                stroke={past ? "var(--viz-wait-2)" : "var(--viz-wait)"} strokeWidth="2" />
            </g>
          );
        })}
        {/* threshold line + right-gutter label */}
        {hline && (
          <g>
            <line x1={pad.l} x2={W - pad.r} y1={y(annual)} y2={y(annual)} stroke="var(--viz-neutral)" strokeWidth="1.5" strokeDasharray="5 4" />
            <text x={W - pad.r + 6} y={y(annual) - 2} fontSize="11" fontWeight="700" fill="var(--ink-2)">{hline.label}</text>
            <text x={W - pad.r + 6} y={y(annual) + 11} fontSize="10.5" fill="var(--ink-3)">{fmtAxisMoney(annual)}</text>
          </g>
        )}
        {/* break-even crossing marker */}
        {vmark ? (
          <g>
            <line x1={x(Number(vmark.x))} x2={x(Number(vmark.x))} y1={y(Number(vmark.y))} y2={h - pad.b}
              stroke="var(--ink)" strokeWidth="1" strokeDasharray="3 3" opacity="0.45" />
            <circle cx={x(Number(vmark.x))} cy={y(Number(vmark.y))} r="5.5" fill="var(--viz-wait-2)" stroke="var(--surface)" strokeWidth="1.5" />
            <text x={x(Number(vmark.x))} y={y(Number(vmark.y)) - 12} textAnchor="middle" fontSize="11.5" fontWeight="700" fill="var(--viz-wait-2)">{vmark.label}</text>
          </g>
        ) : hline && (
          <text x={pad.l + 8} y={pad.t + 14} fontSize="11.5" fontWeight="600" fill="var(--ink-3)">No break-even within 10 years</text>
        )}
      </svg>
      <Legend items={[{ label: s.name, color: "var(--viz-wait)" }]} />
      {node}
    </>
  );
}

/* ---------- dot-interval (backtest) ---------- */
function DotInterval({ spec, h }: { spec: ChartSpec; h: number }) {
  const pad = { l: 80, r: 40, t: 30, b: 40 };
  const model = spec.series.find((s) => /model/i.test(s.name)) ?? spec.series[0];
  const obs = spec.series.find((s) => /observed/i.test(s.name));
  const all = [...nums(model.y_lo), ...nums(model.y_hi), ...nums(model.y), ...(obs ? nums(obs.y) : [])];
  const lo = Math.min(...all) * 0.97, hi = Math.max(...all) * 1.03;
  const y0 = h / 2;
  const x = lin(lo, hi, pad.l, W - pad.r);
  const xTicks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) / 4) * i);
  const mLo = Number(model.y_lo![0]), mHi = Number(model.y_hi![0]), mMid = Number(model.y![0]);
  const obsV = obs ? Number(obs.y![0]) : null;
  // The pass criterion the chart exists to show: observed within the predicted band.
  const passed = spec.pass ?? (obsV != null && obsV >= mLo && obsV <= mHi);
  const passColor = passed ? "#1d9e75" : "var(--viz-wait-2)";
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        {/* pass/fail badge — the chart's whole point, now shown not just captioned */}
        {obsV != null && (
          <g>
            <rect x={pad.l} y={pad.t - 6} width={passed ? 132 : 150} height={22} rx="11" fill={passColor} opacity="0.14" />
            <text x={pad.l + 11} y={pad.t + 9} fontSize="12" fontWeight="700" fill={passColor}>{passed ? "✓ within range — passes" : "✗ outside range"}</text>
          </g>
        )}
        {xTicks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={pad.t + 22} y2={h - pad.b} stroke="var(--grid)" />
            <text x={x(t)} y={h - pad.b + 18} textAnchor="middle" fontSize="12" fill="var(--ink-3)">{fmtNum(t)}</text>
          </g>
        ))}
        {spec.x_unit && <text x={(pad.l + W - pad.r) / 2} y={h - 4} textAnchor="middle" fontSize="11.5" fontWeight="600" fill="var(--ink-3)">{spec.x_unit}</text>}
        <rect x={x(mLo)} y={y0 - 16} width={x(mHi) - x(mLo)} height={32} rx="6" fill={passColor} opacity={0.16} />
        <line x1={x(mLo)} x2={x(mHi)} y1={y0} y2={y0} stroke="var(--viz-act)" strokeWidth="2.5" />
        <circle cx={x(mMid)} cy={y0} r="6" fill="var(--viz-act)" />
        <text x={x(mMid)} y={y0 - 26} textAnchor="middle" fontSize="12.5" fontWeight="700" fill="var(--viz-act)">predicted {fmtNum(mMid)}</text>
        {obsV != null && (
          <g>
            <circle cx={x(obsV)} cy={y0} r="7" fill="none" stroke="var(--ink)" strokeWidth="2.5" />
            <circle cx={x(obsV)} cy={y0} r="2.5" fill="var(--ink)" />
            <text x={x(obsV)} y={y0 + 34} textAnchor="middle" fontSize="12.5" fontWeight="700" fill="var(--ink)">observed {fmtNum(obsV)}</text>
          </g>
        )}
      </svg>
      <Legend items={[
        { label: "Model's predicted range for 2024", color: "var(--viz-act)" },
        { label: "What actually happened (2024 count)", color: "var(--ink)" },
      ]} />
    </>
  );
}

/* ---------- stacked area (compartments) ---------- */
function StackedArea({ spec, h }: { spec: ChartSpec; h: number }) {
  const pad = { l: 60, r: 24, t: 18, b: 44 };
  const xs = nums(spec.series[0].x);
  const stacks = xs.map((_, j) => spec.series.reduce((sum, s) => sum + Number(s.y![j]), 0));
  const hi = niceMax(Math.max(...stacks));
  const x = lin(Math.min(...xs), Math.max(...xs), pad.l, W - pad.r);
  const y = lin(0, hi, h - pad.b, pad.t);
  const yTicks = Array.from({ length: 5 }, (_, i) => (hi / 4) * i);
  const base = xs.map(() => 0);
  const layers = spec.series.map((s, i) => {
    const top = xs.map((xv, j) => { base[j] += Number(s.y![j]); return [x(xv), y(base[j])] as [number, number]; });
    const bot = xs.map((xv, j) => [x(xv), y(base[j] - Number(s.y![j]))] as [number, number]);
    return { d: areaFrom(top, bot), color: vizColor(s.name, i), name: s.name };
  });
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        <Axes x={x} y={y} w={W} h={h} pad={pad} yTicks={yTicks} xTicks={xs}
          yFmt={(t) => `${(t / 1000).toFixed(0)}k`} xFmt={(t) => `Y${t}`} xLabel={spec.x_label} yLabel={spec.y_label} />
        {layers.map((l, i) => <path key={i} d={l.d} fill={l.color} opacity={0.55} stroke="var(--surface)" strokeWidth="0.6" />)}
      </svg>
      <Legend items={layers.map((l) => ({ label: l.name, color: l.color, swatch: true }))} />
    </>
  );
}

/* ---------- categorical bars + CI; delta-from-act-now mode (scenario costs) ---------- */
function BarCI({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const pad = { l: 70, r: 24, t: 26, b: 56 };
  const s = spec.series[0];
  const labels = (s.x ?? []).map(String);
  const ys = nums(s.y), los = nums(s.y_lo), his = nums(s.y_hi);
  const delta = !!spec.delta;
  const robust = s.robust ?? [];
  const absTotals = s.abs_total ?? [];
  const dmin = delta ? Math.min(0, ...los) : 0;
  const hi = niceMax(Math.max(...his) * 1.08);
  const y = lin(dmin, hi, h - pad.b, pad.t);
  const slot = (W - pad.l - pad.r) / labels.length, bw = Math.min(slot * 0.42, 110);
  const ticks = 5;
  const yTicks = Array.from({ length: ticks }, (_, i) => dmin + ((hi - dmin) / (ticks - 1)) * i);
  const y0 = y(0);
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        {yTicks.map((t, i) => (
          <g key={i}><line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={pad.l - 9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="11.5" fill="var(--ink-3)">{fmtAxisMoney(t)}</text></g>
        ))}
        {/* the "acting now = $0" reference baseline */}
        {delta && (
          <g>
            <line x1={pad.l} x2={W - pad.r} y1={y0} y2={y0} stroke="var(--viz-act)" strokeWidth="1.5" />
            <text x={pad.l + 2} y={y0 - 5} fontSize="11" fontWeight="700" fill="var(--viz-act)">Acting now = $0</text>
          </g>
        )}
        {labels.map((lab, i) => {
          const cx = pad.l + slot * i + slot / 2;
          const barTop = Math.min(y(ys[i]), y0), barH = Math.max(2, Math.abs(y(ys[i]) - y0));
          return (
            <g key={i} onMouseMove={(e) => show(e, (
              <div><b>{lab}</b>
                <div className="tip-row"><span className="tip-k">extra vs act now</span><span>{fmtMusd(ys[i])}</span></div>
                <div className="tip-row"><span className="tip-k">80% range</span><span>{fmtMusd(los[i])}–{fmtMusd(his[i])}</span></div>
                {absTotals[i] != null && <div className="tip-row"><span className="tip-k">10-yr total</span><span>{fmtMusd(absTotals[i])}</span></div>}
              </div>))} onMouseLeave={hide}>
              <rect x={cx - bw / 2} y={barTop} width={bw} height={barH} rx="4" fill={vizColor(lab, i)} />
              <line x1={cx} x2={cx} y1={y(his[i])} y2={y(los[i])} stroke="var(--ink)" strokeWidth="1.5" opacity="0.55" />
              <line x1={cx - 7} x2={cx + 7} y1={y(his[i])} y2={y(his[i])} stroke="var(--ink)" strokeWidth="1.5" opacity="0.55" />
              <line x1={cx - 7} x2={cx + 7} y1={y(los[i])} y2={y(los[i])} stroke="var(--ink)" strokeWidth="1.5" opacity="0.55" />
              <text x={cx} y={y(his[i]) - 8} textAnchor="middle" fontSize="12.5" fontWeight="700" fill="var(--ink)">+{fmtMusd(ys[i])}</text>
              <text x={cx} y={h - pad.b + 17} textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--ink-2)">{lab}</text>
              {robust[i] && <text x={cx} y={h - pad.b + 32} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="var(--viz-act)">✓ range excludes $0</text>}
            </g>
          );
        })}
        <line x1={pad.l} x2={W - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      {node}
    </>
  );
}

/* ---------- TRUE waterfall (cost of waiting: baseline -> slice -> total) ---------- */
function Waterfall({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const pad = { l: 72, r: 28, t: 56, b: 46 };
  const s = spec.series[0];
  const labels = (s.x ?? []).map(String);
  const ys = nums(s.y);
  const base = (s.base ?? labels.map(() => 0)).map(Number);
  const measure = s.measure ?? labels.map(() => "absolute");
  const yl = s.y_lo ?? [], yh = s.y_hi ?? [];
  const tops = labels.map((_, i) => base[i] + ys[i]);
  // Broken axis: zoom to the band around the near-equal totals so the small slice
  // (the cost of waiting) is readable. Honesty note required (rendered below).
  const totalsTops = tops.filter((_, i) => measure[i] !== "relative");
  const minV = Math.min(...totalsTops);
  const maxV = Math.max(...tops);
  const span = Math.max(maxV - minV, maxV * 0.01);
  const F = Math.max(0, minV - span * 1.3);
  const hiAxis = maxV + span * 0.6;
  const y = lin(F, hiAxis, h - pad.b, pad.t);
  const slot = (W - pad.l - pad.r) / labels.length, bw = Math.min(slot * 0.42, 130);
  const yTicks = Array.from({ length: 4 }, (_, i) => F + ((hiAxis - F) / 3) * i);
  const colorOf = (m: string) => m === "absolute" ? "var(--viz-act)" : "var(--viz-wait)";
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        {yTicks.map((t, i) => (
          <g key={i}><line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={pad.l - 9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="11.5" fill="var(--ink-3)">{fmtAxisMoney(t)}</text></g>
        ))}
        {/* dashed connectors from each bar top to the next */}
        {labels.map((_, i) => i === 0 ? null : (
          <line key={`c${i}`} x1={pad.l + slot * (i - 1) + slot / 2 + bw / 2} x2={pad.l + slot * i + slot / 2 - bw / 2}
            y1={y(tops[i - 1])} y2={y(tops[i - 1])} stroke="var(--ink-3)" strokeWidth="1" strokeDasharray="4 4" opacity="0.6" />
        ))}
        {labels.map((lab, i) => {
          const cx = pad.l + slot * i + slot / 2;
          const rel = measure[i] === "relative";
          const yTop = y(tops[i]), yBot = y(rel ? base[i] : F);
          const lo = yl[i] != null ? Number(yl[i]) : null, hiW = yh[i] != null ? Number(yh[i]) : null;
          return (
            <g key={i} onMouseMove={(e) => show(e, (
              <div>
                <b>{lab}</b>
                {rel ? (
                  <>
                    <div className="tip-row"><span className="tip-k">extra cost of waiting</span><span>+{fmtAxisMoney(ys[i])}</span></div>
                    {lo != null && hiW != null && <div className="tip-row"><span className="tip-k">80% range</span><span>{fmtAxisMoney(lo - base[i])}–{fmtAxisMoney(hiW - base[i])}</span></div>}
                    <div className="tip-row"><span className="tip-k">what it is</span><span>what waiting adds on top</span></div>
                  </>
                ) : (
                  <>
                    <div className="tip-row"><span className="tip-k">10-year public cost</span><span>{fmtAxisMoney(tops[i])}</span></div>
                    <div className="tip-row"><span className="tip-k">what it is</span><span>{measure[i] === "total" ? "acting now + the waiting penalty" : "the bill you pay either way"}</span></div>
                  </>
                )}
              </div>))} onMouseLeave={hide}>
              <rect x={cx - bw / 2} y={yTop} width={bw} height={Math.max(2, yBot - yTop)} rx="4"
                fill={colorOf(measure[i])} opacity={measure[i] === "total" ? 0.62 : 1} />
              {lo != null && hiW != null && (
                <g stroke="var(--viz-wait-2)" strokeWidth="2">
                  <line x1={cx} x2={cx} y1={y(hiW)} y2={y(lo)} />
                  <line x1={cx - 7} x2={cx + 7} y1={y(hiW)} y2={y(hiW)} />
                  <line x1={cx - 7} x2={cx + 7} y1={y(lo)} y2={y(lo)} />
                </g>
              )}
              {rel ? (() => {
                // The headline number: a clay pill placed ABOVE the whisker cap so the
                // CI line never crosses it. The bar is already labelled "+ cost of
                // waiting" on the x-axis, so the pill stays clean — just the figure.
                const valText = `+${fmtAxisMoney(ys[i])}`;
                const pw = valText.length * 9 + 22;
                const labelY = (hiW != null ? y(hiW) : yTop) - 16;
                return (
                  <g>
                    <rect x={cx - pw / 2} y={labelY - 13} width={pw} height={24} rx="12" fill="var(--viz-wait)" />
                    <text x={cx} y={labelY + 1} textAnchor="middle" fontSize="15" fontWeight="800" fill="#fff" style={{ fontVariantNumeric: "tabular-nums" }}>{valText}</text>
                  </g>
                );
              })() : (
                <text x={cx} y={yTop - 9} textAnchor="middle" fontSize="12.5" fontWeight="700" fill="var(--ink)">{fmtAxisMoney(tops[i])}</text>
              )}
              <text x={cx} y={h - pad.b + 16} textAnchor="middle" fontSize="11.5" fontWeight="600" fill="var(--ink-2)">{lab}</text>
            </g>
          );
        })}
        {/* axis-break glyph (two slashes) signalling the y-axis doesn't start at 0 */}
        {F > 0 && (
          <g stroke="var(--ink-3)" strokeWidth="1.4" fill="none">
            <path d={`M${pad.l - 5} ${h - pad.b - 2} l10 -4`} />
            <path d={`M${pad.l - 5} ${h - pad.b + 3} l10 -4`} />
          </g>
        )}
        <line x1={pad.l} x2={W - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      {F > 0 && <div className="chart-src" style={{ marginTop: 8 }}>Axis starts near {fmtAxisMoney(F)} so the small slice is visible — the two totals are near-equal by design.</div>}
      {node}
    </>
  );
}

/* ---------- vertical bars (budget / mix comparison) ---------- */
function VBar({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const s = spec.series[0];
  const labels = (s.x ?? []).map(String);
  const ys = nums(s.y);
  const pct = isPercentSpec(spec);
  const valFmt = pct ? (v: number) => `${v.toFixed(1)}%` : fmtMusd;
  const axisFmt = pct ? (t: number) => `${Math.round(t)}%` : fmtAxisMoney;

  // Wrap long category names onto two lines so they never collide; widen the
  // bottom gutter only when wrapping actually happens (short money labels stay 1 line).
  const slot0 = (W - 64 - 24) / labels.length;
  const maxChars = Math.max(8, Math.floor(slot0 / 6.6));
  const wrapped = labels.map((l) => wrapLabel(l, maxChars));
  const twoLine = wrapped.some((w) => w.length > 1);
  const pad = { l: 64, r: 24, t: 24, b: twoLine ? 62 : 52 };

  const lo = Math.min(...ys), hiData = Math.max(...ys);
  // Percent/rate charts always baseline at 0 (honest share). Money comparisons may
  // start the axis near the data so near-equal costs stay distinguishable.
  const floor = pct ? 0 : (lo > hiData * 0.5 ? Math.max(0, lo - (hiData - lo) * 0.8) : 0);
  const hi = niceMax(hiData * (pct ? 1.02 : 1.04));
  const y = lin(floor, hi, h - pad.b, pad.t);
  const slot = (W - pad.l - pad.r) / labels.length, bw = Math.min(slot * 0.5, 90);
  const yTicks = Array.from({ length: 5 }, (_, i) => floor + ((hi - floor) / 4) * i);
  // Money: lowest cost = recommended (indigo). Percent: uniform clay (exposure/risk).
  // no_best (roi, people_helped) disables the lowest-bar highlight, which would
  // mis-frame charts where "bigger is better" or the bars aren't ranked.
  const best = (pct || spec.no_best) ? -1 : ys.indexOf(Math.min(...ys));
  const tipLabel = pct ? (s.name || "rate") : "10-yr cost";
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        {yTicks.map((t, i) => (
          <g key={i}><line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={pad.l - 9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--ink-3)">{axisFmt(t)}</text></g>
        ))}
        {labels.map((lab, i) => {
          const cx = pad.l + slot * i + slot / 2;
          const isBest = i === best;
          const fill = s.colors ? s.colors[i] : pct ? "var(--viz-wait)" : isBest ? "var(--viz-act)" : "var(--viz-neutral)";
          const op = s.colors ? 1 : pct ? 0.82 : isBest ? 1 : 0.6;
          return (
            <g key={i} onMouseMove={(e) => show(e, <div><b>{lab}</b><div className="tip-row"><span className="tip-k">{tipLabel}</span><span>{valFmt(ys[i])}</span></div></div>)} onMouseLeave={hide}>
              <rect x={cx - bw / 2} y={y(ys[i])} width={bw} height={(h - pad.b) - y(ys[i])} rx="4" fill={fill} opacity={op} />
              <text x={cx} y={y(ys[i]) - 8} textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--ink)">{valFmt(ys[i])}</text>
              {wrapped[i].map((line, k) => (
                <text key={k} x={cx} y={h - pad.b + 16 + k * 13} textAnchor="middle" fontSize="11" fontWeight={isBest ? 700 : 600} fill={isBest ? "var(--ink)" : "var(--ink-2)"}>{line}</text>
              ))}
            </g>
          );
        })}
        {spec.gap && (() => {
          const g = spec.gap, cxT = pad.l + slot * g.to + slot / 2;
          const yHi = y(Math.max(ys[g.from], ys[g.to])), yLo = y(Math.min(ys[g.from], ys[g.to]));
          const cxF = pad.l + slot * g.from + slot / 2;
          return (
            <g>
              <line x1={Math.min(cxF, cxT)} x2={cxT} y1={yHi} y2={yHi} stroke="var(--viz-wait-2)" strokeWidth="1" strokeDasharray="4 3" opacity="0.7" />
              <line x1={cxT} x2={cxT} y1={yHi} y2={yLo} stroke="var(--viz-wait-2)" strokeWidth="2" />
              <path d={`M${cxT - 4} ${yHi + 6} L${cxT} ${yHi} L${cxT + 4} ${yHi + 6}`} fill="none" stroke="var(--viz-wait-2)" strokeWidth="1.5" />
              <path d={`M${cxT - 4} ${yLo - 6} L${cxT} ${yLo} L${cxT + 4} ${yLo - 6}`} fill="none" stroke="var(--viz-wait-2)" strokeWidth="1.5" />
              <text x={cxT - bw / 2 - 8} y={(yHi + yLo) / 2} textAnchor="end" dominantBaseline="middle" fontSize="12.5" fontWeight="700" fill="var(--viz-wait-2)">{g.label}</text>
            </g>
          );
        })()}
        <line x1={pad.l} x2={W - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      {!pct && !spec.no_best && <div className="chart-src" style={{ marginTop: 8 }}>Lowest-cost option highlighted. Axis starts near the data so small differences are visible.</div>}
      {node}
    </>
  );
}

/* ---------- horizontal bars (city benchmark / equity disparity) ---------- */
function HBar({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const s = spec.series[0];
  const vals = nums(s.x), labels = (s.y ?? []).map(String);
  const isDisparity = /disproportion/i.test(s.name);
  const hl = s.highlight ?? [];
  const pad = { l: isDisparity ? 220 : 70, r: 60, t: 16, b: 30 };
  const rowH = Math.max(20, (h - pad.t - pad.b) / labels.length);
  const hi = niceMax(Math.max(...vals) * 1.05);
  const x = lin(0, hi, pad.l, W - pad.r);
  const refLine = isDisparity ? 1 : null; // 1.0× = fair share
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        {labels.map((lab, i) => {
          const cy = pad.t + rowH * i + rowH / 2;
          const over = isDisparity && vals[i] > 1;
          const sel = !!hl[i];                          // the selected city
          const fill = sel ? "var(--viz-act)"           // highlight the chosen city in indigo
            : over ? "var(--viz-wait-2)" : isDisparity ? "var(--viz-neutral)" : "var(--viz-wait)";
          return (
            <g key={i} onMouseMove={(e) => show(e, <div><b>{lab}</b><div className="tip-row"><span className="tip-k">{s.name}</span><span>{isDisparity ? `${vals[i].toFixed(2)}×` : vals[i].toFixed(1)}</span></div></div>)} onMouseLeave={hide}>
              {/* Label sits just past the RENDERED bar end (never the raw value x):
                  negative / near-zero bars clamp to a 1px stub at the axis, so their
                  label stays in the right gutter instead of drifting back over the
                  axis and city names. Positive bars are unaffected. */}
              {(() => { const barW = Math.max(1, x(vals[i]) - pad.l); return (<>
              <text x={pad.l - 10} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="12" fontWeight={sel ? 800 : 400} fill={sel ? "var(--accent-ink)" : "var(--ink-2)"}>{lab}</text>
              <rect x={pad.l} y={cy - rowH * 0.32} width={barW} height={rowH * 0.64} rx="3"
                fill={fill} opacity={sel ? 1 : (over || !isDisparity ? 0.9 : 0.55)} />
              <text x={pad.l + barW + 6} y={cy} dominantBaseline="middle" fontSize="11.5" fontWeight="700" fill={sel ? "var(--accent-ink)" : "var(--ink-2)"}>{isDisparity ? `${vals[i].toFixed(2)}×` : vals[i].toFixed(1)}</text>
              </>); })()}
            </g>
          );
        })}
        {refLine != null && (
          <g>
            <line x1={x(refLine)} x2={x(refLine)} y1={pad.t} y2={h - pad.b} stroke="var(--ink)" strokeWidth="1.25" strokeDasharray="3 4" />
            <text x={x(refLine)} y={pad.t - 4} textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--ink-2)">fair share (1.0×)</text>
          </g>
        )}
      </svg>
      {isDisparity && <Legend items={[
        { label: "Over-represented (> fair share)", color: "var(--viz-wait-2)", swatch: true },
        { label: "At or below fair share", color: "var(--viz-neutral)", swatch: true },
      ]} />}
      {node}
    </>
  );
}

/* ---------- tornado (sensitivity) ---------- */
function Tornado({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const s = spec.series[0];
  const vals = nums(s.x), labels = (s.y ?? []).map(String), conf = s.conf ?? [];
  const raw = s.raw ?? [], tf = s.tighten_first ?? [];
  const pad = { l: 230, r: 64, t: 16, b: 30 };
  const rowH = Math.max(22, (h - pad.t - pad.b) / labels.length);
  const mag = Math.max(...vals.map(Math.abs)) * 1.1;
  const x = lin(-mag, mag, pad.l, W - pad.r);
  // A dedicated CONFIDENCE ramp (teal-green / gray / gold) — deliberately NOT the
  // indigo/clay decision palette, so a low-confidence bar never reads as "cost of waiting".
  const confColor = (c: string) => c === "high" ? "#1d9e75" : c === "med" ? "var(--viz-neutral)" : "#caa12e";
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        <line x1={x(0)} x2={x(0)} y1={pad.t} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
        {labels.map((lab, i) => {
          const cy = pad.t + rowH * i + rowH / 2;
          const v = vals[i];
          const x0 = Math.min(x(0), x(v)), w = Math.abs(x(v) - x(0));
          const flag = !!tf[i];
          return (
            <g key={i} onMouseMove={(e) => show(e, <div><b>{lab}</b>{raw[i] && <div className="tip-row"><span className="tip-k">transition</span><span>{raw[i]}</span></div>}<div className="tip-row"><span className="tip-k">+20% rate →</span><span>{v > 0 ? "+" : ""}{v.toFixed(1)}% cost</span></div><div className="tip-row"><span className="tip-k">confidence</span><span>{conf[i]}{flag ? " · tighten first" : ""}</span></div></div>)} onMouseLeave={hide}>
              <text x={pad.l - 22} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="11.5" fontWeight={flag ? 700 : 400} fill="var(--ink-2)">{lab}</text>
              {flag && <text x={pad.l - 9} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="12">⚠</text>}
              <rect x={x0} y={cy - rowH * 0.3} width={Math.max(1, w)} height={rowH * 0.6} rx="3" fill={confColor(conf[i] ?? "low")}
                opacity={0.9} stroke={flag ? "var(--ink)" : "none"} strokeWidth={flag ? 1.25 : 0} strokeDasharray={flag ? "3 2" : ""} />
              <text x={v > 0 ? x(v) + 6 : x(v) - 6} y={cy} textAnchor={v > 0 ? "start" : "end"} dominantBaseline="middle" fontSize="11" fontWeight="700" fill="var(--ink-2)">{v > 0 ? "+" : ""}{v.toFixed(1)}%</text>
            </g>
          );
        })}
      </svg>
      <Legend items={[
        { label: "High confidence", color: "#1d9e75", swatch: true },
        { label: "Medium", color: "var(--viz-neutral)", swatch: true },
        { label: "Low — ⚠ tighten first", color: "#caa12e", swatch: true },
      ]} />
      {node}
    </>
  );
}

/* ---------- SHAP bars ---------- */
function ShapBar({ spec, h }: { spec: ChartSpec; h: number }) {
  const s = spec.series[0];
  const vals = nums(s.x), labels = (s.y ?? []).map((l) => prettyFeature(String(l)));
  const pad = { l: 200, r: 60, t: 16, b: 30 };
  const rowH = Math.max(28, (h - pad.t - pad.b) / labels.length);
  const mag = Math.max(...vals.map(Math.abs), 0.1) * 1.1;
  const x = lin(-mag, mag, pad.l, W - pad.r);
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        <line x1={x(0)} x2={x(0)} y1={pad.t} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
        {labels.map((lab, i) => {
          const cy = pad.t + rowH * i + rowH / 2;
          const v = vals[i];
          const x0 = Math.min(x(0), x(v)), w = Math.abs(x(v) - x(0));
          const negligible = Math.abs(v) < 0.05;     // a near-zero feature: don't draw a broken 1px bar
          return (
            <g key={i}>
              <text x={pad.l - 12} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="12"
                fill={negligible ? "var(--ink-3)" : "var(--ink-2)"}>{lab}</text>
              {negligible ? (
                <g>
                  <circle cx={x(0)} cy={cy} r="3" fill="none" stroke="var(--ink-3)" strokeWidth="1.5" />
                  <text x={x(0) + 10} y={cy} dominantBaseline="middle" fontSize="11" fill="var(--ink-3)">no measurable effect here</text>
                </g>
              ) : (
                <>
                  <rect x={x0} y={cy - rowH * 0.28} width={w} height={rowH * 0.56} rx="3"
                    fill={v >= 0 ? "var(--viz-wait)" : "var(--viz-act)"} opacity={0.88} />
                  <text x={v >= 0 ? x(v) + 6 : x(v) - 6} y={cy} textAnchor={v >= 0 ? "start" : "end"} dominantBaseline="middle" fontSize="11.5" fontWeight="700" fill="var(--ink-2)">{v >= 0 ? "+" : ""}{v.toFixed(2)}</text>
                </>
              )}
            </g>
          );
        })}
      </svg>
      <Legend items={[
        { label: "Pushes homelessness up", color: "var(--viz-wait)", swatch: true },
        { label: "Pushes down", color: "var(--viz-act)", swatch: true },
      ]} />
    </>
  );
}

/** Turn a raw model feature name into plain English for the public-facing SHAP chart:
 *  "log_median_home_value" → "Median home value". The "log_" prefix is a modeling
 *  detail (we fit on logs) that a policy reader doesn't need. */
function prettyFeature(name: string): string {
  const t = name.replace(/^log_/, "").replace(/_/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/* ---------- scatter (city housing-cost vs rate) ---------- */
function Scatter({ spec, h }: { spec: ChartSpec; h: number }) {
  const { show, hide, node } = useTip();
  const pad = { l: 60, r: 28, t: 22, b: 48 };
  const pts = (spec.series[0].points ?? []) as Array<{ coc: string; x: number; y: number; highlight: boolean }>;
  const xsv = pts.map((p) => Number(p.x)), ysv = pts.map((p) => Number(p.y));
  const xmax = niceMax(Math.max(...xsv)), ymax = niceMax(Math.max(...ysv) * 1.05);
  const x = lin(0, xmax, pad.l, W - pad.r);
  const y = lin(0, ymax, h - pad.b, pad.t);
  const xTicks = Array.from({ length: 5 }, (_, i) => (xmax / 4) * i);
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  return (
    <>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label={spec.title}>
        {yTicks.map((t, i) => (
          <g key={i}><line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={pad.l - 9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--ink-3)">{t.toFixed(0)}</text></g>
        ))}
        {xTicks.map((t, i) => <text key={i} x={x(t)} y={h - pad.b + 18} textAnchor="middle" fontSize="12" fill="var(--ink-3)">{fmtUsd(t)}</text>)}
        <line x1={pad.l} x2={W - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
        <text x={(pad.l + W - pad.r) / 2} y={h - 4} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)" fontWeight="600">{spec.x_label ?? "Median home value"}</text>
        <text transform={`translate(14 ${(pad.t + h - pad.b) / 2}) rotate(-90)`} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)" fontWeight="600">{spec.y_label ?? "Homeless / 1,000"}</text>
        {/* the trend line the caption claims — now drawn (least-squares over all cities) */}
        {spec.trend && (
          <g>
            <line x1={x(spec.trend.x0)} y1={y(spec.trend.y0)} x2={x(spec.trend.x1)} y2={y(spec.trend.y1)}
              stroke="var(--ink-3)" strokeWidth="1.5" strokeDasharray="6 4" opacity="0.8" />
            <text x={x(spec.trend.x1)} y={y(spec.trend.y1) - 6} textAnchor="end" fontSize="10.5" fill="var(--ink-3)">typical pattern</text>
          </g>
        )}
        {pts.map((p) => (
          <g key={p.coc} onMouseMove={(e) => show(e, <div><b>{p.coc}</b><div className="tip-row"><span className="tip-k">Home value</span><span>{fmtUsd(Number(p.x))}</span></div><div className="tip-row"><span className="tip-k">Rate / 1,000</span><span>{Number(p.y).toFixed(2)}</span></div></div>)} onMouseLeave={hide}>
            <circle cx={x(Number(p.x))} cy={y(Number(p.y))} r={p.highlight ? 7 : 4.5}
              fill={p.highlight ? "var(--viz-act)" : "var(--viz-neutral)"} fillOpacity={p.highlight ? 0.9 : 0.5}
              stroke={p.highlight ? "var(--viz-act)" : "none"} strokeWidth="2" />
            {p.highlight && <text x={x(Number(p.x))} y={y(Number(p.y)) - 12} textAnchor="middle" fontSize="11.5" fontWeight="700" fill="var(--viz-act)">{p.coc}</text>}
          </g>
        ))}
      </svg>
      {node}
    </>
  );
}

/* ---------- map kind (reuses the USMap component) ---------- */
function MapKind({ spec }: { spec: ChartSpec }) {
  const raw = (spec.series[0].points ?? []) as Array<Record<string, any>>;
  const points: CocPoint[] = raw.map((p) => ({
    coc: String(p.coc), name: String(p.coc), lat: Number(p.lat), lon: Number(p.lon),
    pit_total: Number(p.pit_total), population: 0, rate_per_1k: Number(p.rate),
    median_home_value: 0, highlight: Boolean(p.highlight),
  }));
  const sel = points.find((p) => p.highlight)?.coc ?? "";
  return <USMap points={points} selected={sel} />;
}
