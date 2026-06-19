/* ============================================================
   WaitCost — chart primitives + decision charts
   Hand-built SVG. Theme-aware via CSS vars (stroke="var(--viz-*)").
   Colorblind-safe: indigo / warm-gray / amber-clay + structural gray.
   ============================================================ */
var useState = React.useState, useRef = React.useRef, useEffect = React.useEffect, useMemo = React.useMemo, useCallback = React.useCallback;

/* ---------- shared tooltip ---------- */
function useTip() {
  const [tip, setTip] = useState(null);
  const show = useCallback((e, content) => {
    setTip({ x: e.clientX, y: e.clientY, content });
  }, []);
  const hide = useCallback(() => setTip(null), []);
  const node = tip ? (
    <div className="viz-tip" style={{ left: Math.min(tip.x + 14, window.innerWidth - 250), top: tip.y + 14 }}>
      {tip.content}
    </div>
  ) : null;
  return { show, hide, node };
}

/* ---------- scale helpers ---------- */
const lin = (d0, d1, r0, r1) => v => r0 + (r1 - r0) * ((v - d0) / (d1 - d0 || 1));
const niceMax = v => {
  const e = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / e;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * e;
};
function pathFrom(pts) { return pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" "); }
function areaFrom(top, bot) {
  return pathFrom(top) + " L" + bot[bot.length-1][0].toFixed(1) + " " + bot[bot.length-1][1].toFixed(1) +
    " " + bot.slice().reverse().map(p => "L"+p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" ") + " Z";
}

/* ---------- axes frame ---------- */
function Axes({ x, y, w, h, pad, yTicks, xTicks, yFmt, xFmt, yLabel, xLabel }) {
  return (
    <g>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
          <text x={pad.l - 9} y={y(t)} textAnchor="end" dominantBaseline="middle"
            fontSize="12" fill="var(--ink-3)" fontVariantNumeric="tabular-nums">{yFmt(t)}</text>
        </g>
      ))}
      {xTicks.map((t, i) => (
        <text key={i} x={x(t)} y={h - pad.b + 18} textAnchor="middle"
          fontSize="12" fill="var(--ink-3)" fontVariantNumeric="tabular-nums">{xFmt(t)}</text>
      ))}
      <line x1={pad.l} x2={w - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      {xLabel && <text x={(pad.l + w - pad.r) / 2} y={h - 4} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)" fontWeight="600">{xLabel}</text>}
      {yLabel && <text transform={`translate(14 ${(pad.t + h - pad.b)/2}) rotate(-90)`} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)" fontWeight="600">{yLabel}</text>}
    </g>
  );
}

/* draw-in animation for paths (gated to reduced-motion by CSS on parent) */
function useDraw(active) {
  const ref = useRef(null);
  useEffect(() => {
    if (!active || !ref.current) return;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const el = ref.current;
    const len = el.getTotalLength ? el.getTotalLength() : 0;
    if (!len) return;
    el.style.transition = "none";
    el.style.strokeDasharray = len; el.style.strokeDashoffset = len;
    requestAnimationFrame(() => {
      el.style.transition = "stroke-dashoffset 1s var(--ease-out)";
      el.style.strokeDashoffset = "0";
    });
  }, [active]);
  return ref;
}

/* =========================================================================
   1) COST TRAJECTORY — cumulative EXTRA public cost vs. acting now
      (the decision quantity: "act now" is the flat baseline; "delay"
      climbs to the cost of waiting; "do nothing" climbs to the full
      forgone savings). Each path carries a widening P10–P90 band.
   ========================================================================= */
function CostTrajectory({ scn, showBands = true, h = 420, animate = true }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 70, r: 28, t: 22, b: 40 };
  // cumulative extra $ vs acting-now, in $M, by year
  const cumExtra = (arr) => {
    const out = [0]; let acc = 0;
    for (let t = 1; t <= 10; t++) { acc += (arr[t] - scn.actNow[t]) * 1e9; out.push(acc / 1e6); }
    return out;
  };
  const doNothing = cumExtra(scn.statusQuo);   // → actNowSaves
  const delayed = cumExtra(scn.delay_);        // → costOfWaiting
  const actNow = scn.years.map(() => 0);       // baseline
  const widen = (arr, lo, hi) => arr.map((v, t) => ({ p50: v, p10: v * (1 - lo * (1 + t * 0.05)), p90: v * (1 + hi * (1 + t * 0.05)) }));

  const series = [
    { key: "doNothing", arr: doNothing, band: widen(doNothing, 0.20, 0.28), color: "var(--viz-neutral)", bandFill: "var(--viz-band)", label: "Do nothing", dash: "" },
    { key: "delay", arr: delayed, band: widen(delayed, 0.18, 0.19), color: "var(--viz-wait)", bandFill: "var(--viz-band-wait)", label: `Delay ${scn.delay} yr`, dash: "6 5" },
    { key: "actNow", arr: actNow, band: actNow.map(() => ({ p50: 0, p10: 0, p90: 0 })), color: "var(--viz-act)", bandFill: "none", label: "Act now (baseline)", dash: "" },
  ];
  const ymax = niceMax(Math.max(...(showBands ? series[0].band.map(b => b.p90) : doNothing)) * 1.08);
  const x = lin(0, 10, pad.l, w - pad.r);
  const y = lin(0, ymax, h - pad.b, pad.t);
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  const xTicks = scn.years;
  const fmtY = t => t >= 1000 ? "$" + (t / 1000).toFixed(1) + "B" : "$" + Math.round(t) + "M";
  const fmtV = v => v >= 1000 ? "$" + (v / 1000).toFixed(2) + "B" : "$" + Math.round(v) + "M";
  const drawRef = useDraw(animate);

  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img"
        aria-label={`Cumulative extra public cost versus acting now for ${scn.city.name}, over ten years, with uncertainty bands.`}>
        <Axes x={x} y={y} w={w} h={h} pad={pad}
          yTicks={yTicks} xTicks={xTicks}
          yFmt={fmtY} xFmt={t => "Y" + t} xLabel="Years from today" yLabel="Extra public cost vs. acting now" />
        {showBands && series.filter(s => s.bandFill !== "none").map(s => (
          <path key={s.key+"b"} d={areaFrom(
            s.band.map((b, t) => [x(t), y(b.p90)]),
            s.band.map((b, t) => [x(t), y(b.p10)])
          )} fill={s.bandFill} stroke="none" />
        ))}
        {series.map((s, si) => (
          <path key={s.key} ref={s.key === "delay" ? drawRef : null}
            d={pathFrom(s.arr.map((v, t) => [x(t), y(v)]))}
            fill="none" stroke={s.color} strokeWidth={s.key === "actNow" ? 3 : 2.6}
            strokeDasharray={s.dash} strokeLinecap="round" strokeLinejoin="round" />
        ))}
        {scn.years.map(t => (
          <rect key={t} x={x(t) - (w-pad.l-pad.r)/20} y={pad.t} width={(w-pad.l-pad.r)/10} height={h-pad.t-pad.b}
            fill="transparent"
            onMouseMove={e => show(e, (
              <div>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>By year {t}, vs acting now</div>
                <div className="tip-row"><span className="tip-k">Do nothing</span><span>+{fmtV(doNothing[t])}</span></div>
                <div className="tip-row"><span className="tip-k">Delay {scn.delay}y</span><span>+{fmtV(delayed[t])}</span></div>
                <div className="tip-row"><span className="tip-k">Act now</span><span>$0</span></div>
              </div>
            ))}
            onMouseLeave={hide} />
        ))}
        {series.map(s => (
          <g key={s.key+"e"}>
            <circle cx={x(10)} cy={y(s.arr[10])} r="3.8" fill="var(--surface)" stroke={s.color} strokeWidth="2.5" />
            {s.key !== "actNow" && <text x={x(10) - 6} y={y(s.arr[10]) - 9} textAnchor="end" fontSize="12.5" fontWeight="700" fill={s.color}>+{fmtV(s.arr[10])}</text>}
          </g>
        ))}
      </svg>
      <div className="legend" style={{ marginTop: 10 }}>
        {series.map(s => (
          <span key={s.key} className="legend-item">
            <span className="legend-line" style={{ borderTopColor: s.color, borderTopStyle: s.dash ? "dashed" : "solid" }}></span>
            {s.label}
          </span>
        ))}
        {showBands && <span className="legend-item muted"><span className="legend-swatch" style={{ background: "var(--viz-band)" }}></span>P10–P90 range</span>}
      </div>
      {node}
    </div>
  );
}

/* =========================================================================
   2) COST-OF-WAITING WATERFALL — each delay year adds cost
   ========================================================================= */
function Waterfall({ scn, h = 360 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 64, r: 24, t: 20, b: 44 };
  // per-year incremental cost of waiting (build from delay scenarios 1..delay)
  const steps = [];
  let running = 0;
  for (let d = 1; d <= Math.max(scn.delay, 1); d++) {
    const s = WC.computeScenario({ city: scn.city, budget: scn.budget, delay: d, mix: scn.mix });
    const cum = s.costOfWaiting;
    steps.push({ label: `+ Year ${d}`, add: cum - running, cum });
    running = cum;
  }
  const total = running;
  const ymax = niceMax(total * 1.12 / 1e6) * 1e6;
  const y = lin(0, ymax, h - pad.b, pad.t);
  const bw = (w - pad.l - pad.r) / (steps.length + 1) * 0.62;
  const slot = (w - pad.l - pad.r) / (steps.length + 1);
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);

  let acc = 0;
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Waterfall: how each year of delay adds to the cost of waiting.">
        {yTicks.map((t, i) => (
          <g key={i}>
            <line x1={pad.l} x2={w-pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={pad.l-9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--ink-3)">{WC.fmtMoney(t)}</text>
          </g>
        ))}
        {steps.map((s, i) => {
          const x0 = pad.l + slot * i + slot * 0.5 - bw / 2;
          const top = y(s.cum), bottom = y(acc);
          const node2 = (
            <rect key={i} x={x0} y={top} width={bw} height={Math.max(2, bottom - top)} rx="3"
              fill="var(--viz-wait)" opacity={0.55 + i * 0.12}
              onMouseMove={e => show(e, <div><b>Delay through year {i+1}</b><div className="tip-row"><span className="tip-k">Adds</span><span>{WC.fmtMoney(s.add)}</span></div><div className="tip-row"><span className="tip-k">Cumulative</span><span>{WC.fmtMoney(s.cum)}</span></div></div>)}
              onMouseLeave={hide} />
          );
          acc = s.cum;
          return node2;
        })}
        {/* total bar */}
        {(() => {
          const x0 = pad.l + slot * steps.length + slot * 0.5 - bw / 2;
          return <rect x={x0} y={y(total)} width={bw} height={(h-pad.b)-y(total)} rx="3" fill="var(--viz-wait-2)"
            onMouseMove={e => show(e, <div><b>Total cost of waiting</b><div className="tip-row"><span>{WC.fmtMoney(total)}</span></div></div>)} onMouseLeave={hide} />;
        })()}
        {[...steps.map((s,i)=>s.label), "Total"].map((lab, i) => (
          <text key={i} x={pad.l + slot * i + slot * 0.5} y={h - pad.b + 18} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)" fontWeight={i===steps.length?700:400}>{lab}</text>
        ))}
        <line x1={pad.l} x2={w-pad.r} y1={h-pad.b} y2={h-pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      <div className="legend" style={{ marginTop: 10 }}>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--viz-wait)" }}></span>Added by each year of delay</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--viz-wait-2)" }}></span>Total extra 10-yr cost</span>
      </div>
      {node}
    </div>
  );
}

/* =========================================================================
   3) BREAK-EVEN CURVE — cumulative cost: act now vs delay
   ========================================================================= */
function BreakEven({ scn, h = 360 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 60, r: 24, t: 18, b: 42 };
  const cumA = [], cumD = []; let a = 0, d = 0;
  for (let t = 0; t <= 10; t++) {
    if (t > 0) { a += scn.actNow[t]; d += scn.delay_[t]; }
    cumA.push(a); cumD.push(d);
  }
  const ymax = niceMax(Math.max(cumD[10], cumA[10]) * 1.05);
  const x = lin(0, 10, pad.l, w - pad.r);
  const y = lin(0, ymax, h - pad.b, pad.t);
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  const be = scn.breakEvenYear;
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Break-even: cumulative cost of acting now versus delaying.">
        <Axes x={x} y={y} w={w} h={h} pad={pad} yTicks={yTicks} xTicks={scn.years}
          yFmt={t => "$"+t.toFixed(0)+"B"} xFmt={t => "Y"+t} xLabel="Years from today" />
        <path d={areaFrom(cumD.map((v,t)=>[x(t),y(v)]), cumA.map((v,t)=>[x(t),y(v)]))} fill="var(--viz-band-wait)" />
        <path d={pathFrom(cumD.map((v,t)=>[x(t),y(v)]))} fill="none" stroke="var(--viz-wait)" strokeWidth="2.6" strokeDasharray="6 5" />
        <path d={pathFrom(cumA.map((v,t)=>[x(t),y(v)]))} fill="none" stroke="var(--viz-act)" strokeWidth="3" />
        {be && <g>
          <line x1={x(be)} x2={x(be)} y1={pad.t} y2={h-pad.b} stroke="var(--ink-3)" strokeWidth="1" strokeDasharray="3 4" />
          <circle cx={x(be)} cy={y(cumA[be])} r="4.5" fill="var(--viz-act)" />
          <text x={x(be)} y={pad.t + 4} textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--ink-2)">Break-even · Y{be}</text>
        </g>}
      </svg>
      <div className="legend" style={{ marginTop: 10 }}>
        <span className="legend-item"><span className="legend-line" style={{ borderTopColor: "var(--viz-act)" }}></span>Act now (cumulative)</span>
        <span className="legend-item"><span className="legend-line" style={{ borderTopColor: "var(--viz-wait)", borderTopStyle: "dashed" }}></span>Delay {scn.delay}y (cumulative)</span>
      </div>
      {node}
    </div>
  );
}

/* =========================================================================
   4) SCENARIO BARS — 10-yr cost by path with ranges
   ========================================================================= */
function ScenarioBars({ scn, h = 340 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 64, r: 24, t: 20, b: 44 };
  const sqCum = scn.statusQuo10;
  const actCum = sqCum - scn.actNowSaves;
  const delCum = actCum + scn.costOfWaiting;
  const bars = [
    { label: "Act now", v: actCum, lo: actCum*0.86, hi: actCum*1.16, color: "var(--viz-act)" },
    { label: `Delay ${scn.delay}y`, v: delCum, lo: delCum*0.86, hi: delCum*1.16, color: "var(--viz-wait)" },
    { label: "Status quo", v: sqCum, lo: scn.statusQuo10Lo, hi: scn.statusQuo10Hi, color: "var(--viz-neutral)" },
  ];
  const ymax = niceMax(Math.max(...bars.map(b => b.hi)) / 1e9) * 1e9;
  const y = lin(0, ymax, h - pad.b, pad.t);
  const slot = (w - pad.l - pad.r) / bars.length;
  const bw = slot * 0.46;
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Ten-year public cost by path, with uncertainty ranges.">
        {yTicks.map((t,i)=>(<g key={i}><line x1={pad.l} x2={w-pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" /><text x={pad.l-9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--ink-3)">{WC.fmtMoney(t)}</text></g>))}
        {bars.map((b, i) => {
          const cx = pad.l + slot * i + slot / 2;
          return (
            <g key={i} onMouseMove={e => show(e, <div><b>{b.label}</b><div className="tip-row"><span className="tip-k">10-yr cost</span><span>{WC.fmtMoney(b.v)}</span></div><div className="tip-row"><span className="tip-k">Range</span><span>{WC.fmtMoney(b.lo)}–{WC.fmtMoney(b.hi)}</span></div></div>)} onMouseLeave={hide}>
              <rect x={cx - bw/2} y={y(b.v)} width={bw} height={(h-pad.b)-y(b.v)} rx="4" fill={b.color} />
              <line x1={cx} x2={cx} y1={y(b.hi)} y2={y(b.lo)} stroke="var(--ink)" strokeWidth="1.5" opacity=".55" />
              <line x1={cx-7} x2={cx+7} y1={y(b.hi)} y2={y(b.hi)} stroke="var(--ink)" strokeWidth="1.5" opacity=".55" />
              <line x1={cx-7} x2={cx+7} y1={y(b.lo)} y2={y(b.lo)} stroke="var(--ink)" strokeWidth="1.5" opacity=".55" />
              <text x={cx} y={y(b.v)-9} textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--ink)">{WC.fmtMoney(b.v)}</text>
              <text x={cx} y={h-pad.b+18} textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--ink-2)">{b.label}</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={w-pad.r} y1={h-pad.b} y2={h-pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      {node}
    </div>
  );
}

/* =========================================================================
   5) COMPARTMENTS OVER TIME — stacked area (at-risk/sheltered/unsheltered/housed)
   ========================================================================= */
function Compartments({ scn, h = 380 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 56, r: 24, t: 18, b: 42 };
  const c = scn.city;
  // simple flow: under "act now", unsheltered declines, housed grows.
  const yrs = scn.years;
  const data = yrs.map(t => {
    const r = 1 - Math.exp(-t / scn.tau);
    const unsheltered = c.unsheltered * (1 - 0.45 * r * (scn.budget/15));
    const sheltered = c.sheltered * (1 + 0.10 * r);
    const housed = (c.unsheltered + c.sheltered) * 0.55 * r * (scn.budget/15);
    const atrisk = c.homeless * 0.8 * (1 - 0.2 * r);
    return { t, atrisk, sheltered, unsheltered, housed };
  });
  const keys = [
    { k:"atrisk", label:"At risk", color:"var(--viz-neutral)", op:.5 },
    { k:"sheltered", label:"Sheltered", color:"var(--viz-act)", op:.45 },
    { k:"unsheltered", label:"Unsheltered", color:"var(--viz-wait)", op:.6 },
    { k:"housed", label:"Newly housed", color:"var(--viz-act)", op:.9 },
  ];
  const ymax = niceMax(Math.max(...data.map(d => keys.reduce((s,k)=>s+d[k.k],0))));
  const x = lin(0, 10, pad.l, w - pad.r);
  const y = lin(0, ymax, h - pad.b, pad.t);
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  let stackBase = data.map(() => 0);
  const layers = keys.map(key => {
    const top = data.map((d, i) => { stackBase[i] += d[key.k]; return [x(d.t), y(stackBase[i])]; });
    const bot = data.map((d, i) => [x(d.t), y(stackBase[i] - d[key.k])]);
    return { key, d: areaFrom(top, bot) };
  });
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Population compartments over time under acting now.">
        <Axes x={x} y={y} w={w} h={h} pad={pad} yTicks={yTicks} xTicks={yrs}
          yFmt={t => (t/1000).toFixed(0)+"k"} xFmt={t => "Y"+t} xLabel="Years from today" />
        {layers.map((l,i) => <path key={i} d={l.d} fill={l.key.color} opacity={l.key.op} stroke="var(--surface)" strokeWidth="0.6" />)}
      </svg>
      <div className="legend" style={{ marginTop: 10 }}>
        {keys.map(k => <span key={k.k} className="legend-item"><span className="legend-swatch" style={{ background: k.color, opacity: k.op }}></span>{k.label}</span>)}
      </div>
      {node}
    </div>
  );
}

/* =========================================================================
   6) BUDGET COMPARISON — cost of waiting across program sizes
   ========================================================================= */
function BudgetCompare({ scn, h = 340 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 64, r: 24, t: 20, b: 44 };
  const sizes = [5, 10, 15, 25, 40];
  const data = sizes.map(b => ({ b, cow: WC.computeScenario({ city: scn.city, budget: b, delay: scn.delay, mix: scn.mix }).costOfWaiting }));
  const ymax = niceMax(Math.max(...data.map(d => d.cow)) / 1e6) * 1e6;
  const y = lin(0, ymax, h - pad.b, pad.t);
  const slot = (w - pad.l - pad.r) / data.length;
  const bw = slot * 0.5;
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Cost of waiting across program sizes.">
        {yTicks.map((t,i)=>(<g key={i}><line x1={pad.l} x2={w-pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" /><text x={pad.l-9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--ink-3)">{WC.fmtMoney(t)}</text></g>))}
        {data.map((d, i) => {
          const cx = pad.l + slot * i + slot/2;
          const cur = d.b === scn.budget;
          return (
            <g key={i} onMouseMove={e => show(e, <div><b>${d.b}M / yr program</b><div className="tip-row"><span className="tip-k">Cost of waiting {scn.delay}y</span><span>{WC.fmtMoney(d.cow)}</span></div></div>)} onMouseLeave={hide}>
              <rect x={cx-bw/2} y={y(d.cow)} width={bw} height={(h-pad.b)-y(d.cow)} rx="4" fill={cur ? "var(--viz-act)" : "var(--viz-neutral)"} opacity={cur?1:.55} />
              <text x={cx} y={h-pad.b+18} textAnchor="middle" fontSize="12" fontWeight={cur?700:600} fill={cur?"var(--ink)":"var(--ink-2)"}>${d.b}M</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={w-pad.r} y1={h-pad.b} y2={h-pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      <div className="chart-src" style={{marginTop:8}}>Highlighted bar = your current program size (${scn.budget}M/yr).</div>
      {node}
    </div>
  );
}

/* =========================================================================
   7) INTERVENTION MIX — grouped outcome by blend
   ========================================================================= */
function MixCompare({ scn, h = 340 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 64, r: 24, t: 20, b: 56 };
  const mixes = [
    { label: "Prevention-led", mix: { prev:0.6, rrh:0.25, psh:0.15 } },
    { label: "Balanced", mix: { prev:0.34, rrh:0.33, psh:0.33 } },
    { label: "Rapid-rehousing", mix: { prev:0.2, rrh:0.6, psh:0.2 } },
    { label: "Housing-led", mix: { prev:0.15, rrh:0.25, psh:0.6 } },
  ];
  const data = mixes.map(m => ({ ...m, saves: WC.computeScenario({ city: scn.city, budget: scn.budget, delay: scn.delay, mix: m.mix }).actNowSaves }));
  const ymax = niceMax(Math.max(...data.map(d => d.saves)) / 1e9) * 1e9;
  const y = lin(0, ymax, h - pad.b, pad.t);
  const slot = (w - pad.l - pad.r) / data.length;
  const bw = slot * 0.5;
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="10-year savings by intervention mix.">
        {yTicks.map((t,i)=>(<g key={i}><line x1={pad.l} x2={w-pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" /><text x={pad.l-9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--ink-3)">{WC.fmtMoney(t)}</text></g>))}
        {data.map((d, i) => {
          const cx = pad.l + slot * i + slot/2;
          return (
            <g key={i} onMouseMove={e => show(e, <div><b>{d.label}</b><div className="tip-row"><span className="tip-k">10-yr savings vs nothing</span><span>{WC.fmtMoney(d.saves)}</span></div></div>)} onMouseLeave={hide}>
              <rect x={cx-bw/2} y={y(d.saves)} width={bw} height={(h-pad.b)-y(d.saves)} rx="4" fill="var(--viz-act)" opacity={0.55 + i*0.12} />
              <text x={cx} y={h-pad.b+18} textAnchor="middle" fontSize="11.5" fontWeight="600" fill="var(--ink-2)">{d.label}</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={w-pad.r} y1={h-pad.b} y2={h-pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      <div className="chart-src" style={{marginTop:8}}>Housing-led blends ramp slower but reach a higher savings ceiling — an assumption with wide uncertainty.</div>
      {node}
    </div>
  );
}

Object.assign(window, {
  useTip, lin, niceMax, pathFrom, areaFrom, Axes, useDraw,
  CostTrajectory, Waterfall, BreakEven, ScenarioBars, Compartments, BudgetCompare, MixCompare,
});
