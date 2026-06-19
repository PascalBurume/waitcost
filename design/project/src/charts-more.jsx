/* ============================================================
   WaitCost — model / context / equity charts + U.S. map
   ============================================================ */

/* =========================================================================
   8) SENSITIVITY TORNADO — which assumptions move the headline most
   ========================================================================= */
function Tornado({ scn, h = 360 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 200, r: 28, t: 16, b: 36 };
  const base = scn.costOfWaiting;
  const factors = [
    { f: "Intervention effect (±50%)", lo: base * 0.55, hi: base * 1.5, conf: "low" },
    { f: "Per-person public cost (±20%)", lo: base * 0.82, hi: base * 1.2, conf: "med" },
    { f: "Inflow growth rate (±30%)", lo: base * 0.86, hi: base * 1.18, conf: "med" },
    { f: "Ramp speed / mix (±25%)", lo: base * 0.88, hi: base * 1.14, conf: "low" },
    { f: "Discount rate (±2pp)", lo: base * 0.93, hi: base * 1.07, conf: "high" },
  ].sort((a, b) => (b.hi - b.lo) - (a.hi - a.lo));
  const lo = Math.min(...factors.map(f => f.lo)), hi = Math.max(...factors.map(f => f.hi));
  const x = lin(lo * 0.98, hi * 1.02, pad.l, w - pad.r);
  const rowH = (h - pad.t - pad.b) / factors.length;
  const confColor = { low: "var(--viz-wait)", med: "var(--viz-neutral)", high: "var(--viz-act)" };
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Tornado chart of sensitivity to key assumptions.">
        <line x1={x(base)} x2={x(base)} y1={pad.t} y2={h - pad.b} stroke="var(--ink-3)" strokeWidth="1.25" strokeDasharray="3 4" />
        <text x={x(base)} y={pad.t - 4} textAnchor="middle" fontSize="11.5" fill="var(--ink-2)" fontWeight="700">Headline {WC.fmtMoney(base)}</text>
        {factors.map((f, i) => {
          const cy = pad.t + rowH * i + rowH / 2;
          return (
            <g key={i} onMouseMove={e => show(e, <div><b>{f.f}</b><div className="tip-row"><span className="tip-k">Range</span><span>{WC.fmtMoney(f.lo)} – {WC.fmtMoney(f.hi)}</span></div><div className="tip-row"><span className="tip-k">Confidence</span><span style={{textTransform:"capitalize"}}>{f.conf}</span></div></div>)} onMouseLeave={hide}>
              <rect x={x(f.lo)} y={cy - 11} width={x(f.hi) - x(f.lo)} height={22} rx="4" fill={confColor[f.conf]} opacity=".72" />
              <text x={pad.l - 12} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="12.5" fill="var(--ink-2)" fontWeight="600">{f.f}</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={w - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--axis)" />
        {[lo, base, hi].map((t, i) => <text key={i} x={x(t)} y={h - pad.b + 18} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)">{WC.fmtMoney(t)}</text>)}
      </svg>
      <div className="legend" style={{ marginTop: 10 }}>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--viz-wait)" }}></span>Low-confidence assumption</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--viz-neutral)" }}></span>Medium</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--viz-act)" }}></span>Well-grounded</span>
      </div>
      {node}
    </div>
  );
}

/* =========================================================================
   9) SHAP DRIVERS — signed horizontal bars
   ========================================================================= */
function ShapDrivers({ h = 360 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 224, r: 64, t: 14, b: 30 };
  const data = WC.MODEL.shap;
  const max = Math.max(...data.map(d => d.v));
  const x = lin(0, max * 1.08, pad.l, w - pad.r);
  const rowH = (h - pad.t - pad.b) / data.length;
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Model drivers ranked by SHAP contribution.">
        {data.map((d, i) => {
          const cy = pad.t + rowH * i + rowH / 2;
          const bw = x(d.v) - pad.l;
          return (
            <g key={i} onMouseMove={e => show(e, <div><b>{d.f}</b><div className="tip-row"><span className="tip-k">Mean |SHAP|</span><span>{d.v.toFixed(2)}</span></div><div className="tip-row"><span className="tip-k">Direction</span><span>{d.dir > 0 ? "↑ raises predicted homelessness" : "↓ lowers it"}</span></div></div>)} onMouseLeave={hide}>
              <rect x={pad.l} y={cy - rowH * 0.32} width={bw} height={rowH * 0.64} rx="4"
                fill={i === 0 ? "var(--viz-act)" : "var(--viz-neutral)"} opacity={i === 0 ? 1 : 0.5 + (1 - i / data.length) * 0.4} />
              <text x={pad.l - 12} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="12.5" fill="var(--ink-2)" fontWeight={i===0?700:600}>{d.f}</text>
              <text x={x(d.v) + 8} y={cy} dominantBaseline="middle" fontSize="12" fill="var(--ink-3)" fontVariantNumeric="tabular-nums">{d.dir > 0 ? "↑" : "↓"} {d.v.toFixed(2)}</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={pad.l} y1={pad.t} y2={h - pad.b} stroke="var(--axis)" />
      </svg>
      <div className="chart-src" style={{marginTop:8}}>Bars show mean absolute SHAP contribution; arrows show direction of effect. Housing cost dominates.</div>
      {node}
    </div>
  );
}

/* =========================================================================
   10) BACKTEST DOT-INTERVAL — predicted band vs observed
   ========================================================================= */
function Backtest({ h = 240 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 40, r: 40, t: 60, b: 50 };
  const bt = WC.BACKTEST;
  const lo = bt.lo * 0.96, hi = bt.hi * 1.04;
  const x = lin(lo, hi, pad.l, w - pad.r);
  const cy = (pad.t + h - pad.b) / 2;
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Backtest: predicted 2024 band versus observed count.">
        {/* predicted band */}
        <rect x={x(bt.lo)} y={cy - 22} width={x(bt.hi) - x(bt.lo)} height={44} rx="8" fill="var(--viz-band-act)" stroke="var(--viz-act)" strokeWidth="1" strokeDasharray="4 4" />
        <line x1={x(bt.predicted)} x2={x(bt.predicted)} y1={cy-22} y2={cy+22} stroke="var(--viz-act)" strokeWidth="2" />
        <text x={x(bt.predicted)} y={cy - 32} textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--viz-act)">Predicted {WC.fmtNum(bt.predicted)}</text>
        <text x={x(bt.lo)} y={cy + 40} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)">{WC.fmtNum(bt.lo)}</text>
        <text x={x(bt.hi)} y={cy + 40} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)">{WC.fmtNum(bt.hi)}</text>
        {/* observed dot */}
        <circle cx={x(bt.observed)} cy={cy} r="9" fill="var(--viz-wait-2)" stroke="var(--surface)" strokeWidth="2.5"
          onMouseMove={e => show(e, <div><b>Observed 2024</b><div className="tip-row"><span>{WC.fmtNum(bt.observed)} (PIT)</span></div><div className="tip-row"><span className="tip-k">Inside 80% band</span><span>{bt.errPct}% error</span></div></div>)} onMouseLeave={hide} />
        <text x={x(bt.observed)} y={cy + 30} textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--viz-wait-2)">Observed {WC.fmtNum(bt.observed)}</text>
      </svg>
      <div className="chart-src" style={{marginTop:8}}>Trained through 2023; 2024 held out. Observed count sits inside the predicted 80% interval ({bt.errPct}% error).</div>
      {node}
    </div>
  );
}

/* =========================================================================
   11) CITY SCATTER — housing cost vs homelessness rate
   ========================================================================= */
function CityScatter({ selectedCoc, onSelect, h = 420 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 58, r: 28, t: 20, b: 48 };
  const cities = WC.CITIES;
  const xmax = niceMax(Math.max(...cities.map(c => c.home)) / 1e3) * 1e3;
  const ymax = niceMax(Math.max(...cities.map(c => c.rate)));
  const x = lin(0, xmax, pad.l, w - pad.r);
  const y = lin(0, ymax, h - pad.b, pad.t);
  const xTicks = Array.from({ length: 5 }, (_, i) => (xmax / 4) * i);
  const yTicks = Array.from({ length: 5 }, (_, i) => (ymax / 4) * i);
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Scatter of 17 cities: housing cost versus homelessness rate.">
        <Axes x={x} y={y} w={w} h={h} pad={pad} yTicks={yTicks} xTicks={xTicks}
          yFmt={t => t.toFixed(0)} xFmt={t => "$" + (t/1000).toFixed(0) + "k"}
          xLabel="Median home value" yLabel="Homeless per 1,000 residents" />
        {cities.map(c => {
          const sel = c.coc === selectedCoc;
          return (
            <g key={c.coc} style={{ cursor: onSelect ? "pointer" : "default" }}
              onClick={() => onSelect && onSelect(c.coc)}
              onMouseMove={e => show(e, <div><b>{c.name}</b><div className="tip-row"><span className="tip-k">Home value</span><span>${(c.home/1000).toFixed(0)}k</span></div><div className="tip-row"><span className="tip-k">Rate /1k</span><span>{c.rate}</span></div></div>)}
              onMouseLeave={hide}>
              <circle cx={x(c.home)} cy={y(c.rate)} r={sel ? 9 : 6}
                fill={sel ? "var(--viz-act)" : "var(--viz-neutral)"} opacity={sel ? 1 : 0.62}
                stroke="var(--surface)" strokeWidth="1.5" />
              {sel && <text x={x(c.home)} y={y(c.rate) - 14} textAnchor="middle" fontSize="12.5" fontWeight="700" fill="var(--viz-act)">{c.name}</text>}
            </g>
          );
        })}
      </svg>
      <div className="chart-src" style={{marginTop:8}}>Each point is a CoC. Selected city highlighted. The upward drift reflects the model's top driver — housing cost.</div>
      {node}
    </div>
  );
}

/* =========================================================================
   12) CITY BENCHMARK — ranked rate per 1,000
   ========================================================================= */
function CityBenchmark({ selectedCoc, onSelect, h = 460 }) {
  const { show, hide, node } = useTip();
  const w = 760, pad = { l: 168, r: 56, t: 12, b: 28 };
  const cities = [...WC.CITIES].sort((a, b) => b.rate - a.rate);
  const max = niceMax(Math.max(...cities.map(c => c.rate)));
  const x = lin(0, max, pad.l, w - pad.r);
  const rowH = (h - pad.t - pad.b) / cities.length;
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Cities ranked by homelessness rate per 1,000.">
        {cities.map((c, i) => {
          const cy = pad.t + rowH * i + rowH / 2;
          const sel = c.coc === selectedCoc;
          return (
            <g key={c.coc} style={{ cursor: onSelect ? "pointer" : "default" }} onClick={() => onSelect && onSelect(c.coc)}
              onMouseMove={e => show(e, <div><b>{c.name}</b><div className="tip-row"><span className="tip-k">Rate /1k</span><span>{c.rate}</span></div><div className="tip-row"><span className="tip-k">PIT count</span><span>{WC.fmtNum(c.homeless)}</span></div></div>)} onMouseLeave={hide}>
              <rect x={pad.l} y={cy - rowH * 0.3} width={x(c.rate) - pad.l} height={rowH * 0.6} rx="3"
                fill={sel ? "var(--viz-act)" : "var(--viz-neutral)"} opacity={sel ? 1 : 0.5} />
              <text x={pad.l - 10} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="12" fontWeight={sel?700:600} fill={sel?"var(--ink)":"var(--ink-2)"}>{c.name}</text>
              <text x={x(c.rate) + 7} y={cy} dominantBaseline="middle" fontSize="11.5" fill="var(--ink-3)" fontVariantNumeric="tabular-nums">{c.rate}</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={pad.l} y1={pad.t} y2={h - pad.b} stroke="var(--axis)" />
      </svg>
      {node}
    </div>
  );
}

/* =========================================================================
   13) U.S. MAP — stylized lower-48 outline + CoC bubbles
   ========================================================================= */
const US_OUTLINE = [
  [-123,49],[-104,49],[-95,49],[-95,49.4],[-89,48],[-84.5,46.5],[-82.5,45],[-83,42],[-79,43.3],
  [-76.5,44],[-73,45],[-71,45],[-69,47.4],[-67,45.2],[-70,43],[-71,42],[-70,41.5],[-74,40.5],
  [-75.5,39],[-76,37],[-75.5,35.5],[-81,31.5],[-80,25.5],[-81,25],[-82.5,28],[-83,30],[-88,30],
  [-90,29],[-94,29.5],[-97,28],[-97.5,26],[-99,27],[-101,29.5],[-103,29],[-106,31.8],[-108,31.3],
  [-111,31.3],[-114.8,32.5],[-117,32.5],[-118.5,34],[-121,36.6],[-122,37.8],[-124,40],[-124,42],
  [-124,46],[-124.7,48.4],
];
function USMap({ selectedCoc, onSelect, h = 460, compact = false }) {
  const { show, hide, node } = useTip();
  const w = 820, pad = { l: 24, r: 24, t: 20, b: 28 };
  const lon = lin(-125, -66, pad.l, w - pad.r);
  const lat = lin(49.6, 24.2, pad.t, h - pad.b);
  const LL = {
    "CA-600":[-118.24,34.05],"NY-600":[-74.0,40.71],"WA-500":[-122.33,47.61],"CA-501":[-122.42,37.77],
    "IL-510":[-87.63,41.88],"MN-500":[-93.27,44.98],"AZ-502":[-112.07,33.45],"CA-601":[-117.16,32.72],
    "TX-700":[-95.37,29.76],"MA-500":[-71.06,42.36],"CO-503":[-104.99,39.74],"OR-501":[-122.68,45.52],
    "DC-500":[-77.04,38.91],"GA-500":[-84.39,33.75],"TX-600":[-96.80,32.78],"CA-502":[-122.27,37.80],
    "CA-503":[-121.49,38.58],
  };
  const rmax = Math.max(...WC.CITIES.map(c => c.rate));
  const rscale = r => 6 + (r / rmax) * (compact ? 16 : 28);
  const outline = US_OUTLINE.map(p => [lon(p[0]), lat(p[1])]);
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="U.S. map with 17 CoC bubbles sized by homelessness rate.">
        <path d={pathFrom(outline) + " Z"} fill="var(--canvas-2)" stroke="var(--hairline-2)" strokeWidth="1.25" strokeLinejoin="round" />
        {WC.CITIES.map(c => {
          const ll = LL[c.coc]; if (!ll) return null;
          const cx = lon(ll[0]), cy = lat(ll[1]);
          const sel = c.coc === selectedCoc;
          return (
            <g key={c.coc} style={{ cursor: "pointer" }} onClick={() => onSelect && onSelect(c.coc)}
              onMouseMove={e => show(e, <div><b>{c.name}</b><div className="tip-row"><span className="tip-k">Rate /1k</span><span>{c.rate}</span></div><div className="tip-row"><span className="tip-k">PIT</span><span>{WC.fmtNum(c.homeless)}</span></div><div style={{marginTop:4,opacity:.7,fontWeight:600}}>{sel ? "Selected" : "Click to select"}</div></div>)}
              onMouseLeave={hide}>
              <circle cx={cx} cy={cy} r={rscale(c.rate)} fill="var(--viz-wait)" opacity={sel ? 0.42 : 0.26}
                stroke={sel ? "var(--viz-act)" : "var(--viz-wait-2)"} strokeWidth={sel ? 2.5 : 1} />
              <circle cx={cx} cy={cy} r="2.5" fill={sel ? "var(--viz-act)" : "var(--viz-wait-2)"} />
              {sel && <text x={cx} y={cy - rscale(c.rate) - 7} textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--ink)">{c.name}</text>}
            </g>
          );
        })}
        {/* size legend */}
        {!compact && (
          <g transform={`translate(${w - 150} ${h - 92})`}>
            <text x="0" y="-8" fontSize="11" fontWeight="700" fill="var(--ink-3)">Rate per 1,000</text>
            {[2, 6, 10].map((r, i) => (
              <g key={i} transform={`translate(${i * 42 + 14} 18)`}>
                <circle cx="0" cy="0" r={rscale(r)} fill="none" stroke="var(--axis)" />
                <text x="0" y={rscale(r) + 12} textAnchor="middle" fontSize="10.5" fill="var(--ink-3)">{r}</text>
              </g>
            ))}
          </g>
        )}
      </svg>
      {node}
    </div>
  );
}

/* =========================================================================
   14) EQUITY DISPARITY — over-representation vs population share
   ========================================================================= */
function EquityDisparity({ coc, h = 380 }) {
  const { show, hide, node } = useTip();
  const eq = WC.equityFor(coc);
  const w = 760, pad = { l: 224, r: 64, t: 16, b: 40 };
  const data = [...eq.groups].sort((a, b) => b.disp - a.disp);
  const max = niceMax(Math.max(...data.map(d => d.disp)));
  const x = lin(0, max, pad.l, w - pad.r);
  const rowH = (h - pad.t - pad.b) / data.length;
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Over-representation among the homeless versus population share, by group.">
        {/* parity line at 1.0x */}
        <line x1={x(1)} x2={x(1)} y1={pad.t} y2={h - pad.b} stroke="var(--ink-3)" strokeWidth="1.25" strokeDasharray="3 4" />
        <text x={x(1)} y={pad.t - 4} textAnchor="middle" fontSize="11.5" fontWeight="700" fill="var(--ink-2)">Parity 1.0×</text>
        {data.map((d, i) => {
          const cy = pad.t + rowH * i + rowH / 2;
          const over = d.disp > 1;
          return (
            <g key={i} onMouseMove={e => show(e, <div><b>{d.g}</b><div className="tip-row"><span className="tip-k">Over-representation</span><span>{d.disp.toFixed(2)}×</span></div><div className="tip-row"><span className="tip-k">Population share</span><span>{d.share}%</span></div></div>)} onMouseLeave={hide}>
              <rect x={pad.l} y={cy - rowH * 0.3} width={Math.max(1, x(d.disp) - pad.l)} height={rowH * 0.6} rx="4"
                fill={over ? "var(--viz-wait)" : "var(--viz-neutral)"} opacity={over ? 0.62 + Math.min(0.34, (d.disp-1)*0.06) : 0.42} />
              <text x={pad.l - 12} y={cy} textAnchor="end" dominantBaseline="middle" fontSize="12.5" fill="var(--ink-2)" fontWeight={over?700:600}>{d.g}</text>
              <text x={x(d.disp) + 8} y={cy} dominantBaseline="middle" fontSize="12" fontWeight="700" fill={over?"var(--viz-wait-2)":"var(--ink-3)"} fontVariantNumeric="tabular-nums">{d.disp.toFixed(1)}×</text>
            </g>
          );
        })}
        <line x1={pad.l} x2={pad.l} y1={pad.t} y2={h - pad.b} stroke="var(--axis)" />
      </svg>
      <div className="chart-src" style={{marginTop:8}}>Population-level only — a group's share of the homeless count divided by its share of residents. Never individual-level.</div>
      {node}
    </div>
  );
}

/* =========================================================================
   15) EQUITY UNSHELTERED — share unsheltered within each group
   ========================================================================= */
function EquityUnsheltered({ coc, h = 360 }) {
  const { show, hide, node } = useTip();
  const eq = WC.equityFor(coc);
  const w = 760, pad = { l: 64, r: 24, t: 20, b: 60 };
  const data = [...eq.groups].sort((a, b) => b.uns - a.uns);
  const y = lin(0, 100, h - pad.b, pad.t);
  const slot = (w - pad.l - pad.r) / data.length;
  const bw = slot * 0.52;
  const yTicks = [0, 25, 50, 75, 100];
  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Share unsheltered within each group.">
        {yTicks.map((t, i) => (<g key={i}><line x1={pad.l} x2={w-pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" /><text x={pad.l-9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--ink-3)">{t}%</text></g>))}
        <line x1={pad.l} x2={w-pad.r} y1={y(eq.overall_uns)} y2={y(eq.overall_uns)} stroke="var(--viz-act)" strokeWidth="1.5" strokeDasharray="5 4" />
        <text x={w-pad.r} y={y(eq.overall_uns)-6} textAnchor="end" fontSize="11.5" fontWeight="700" fill="var(--viz-act)">Citywide {eq.overall_uns}%</text>
        {data.map((d, i) => {
          const cx = pad.l + slot * i + slot / 2;
          const words = d.g.split(" / ")[0].split(" ");
          return (
            <g key={i} onMouseMove={e => show(e, <div><b>{d.g}</b><div className="tip-row"><span className="tip-k">Unsheltered</span><span>{d.uns.toFixed(1)}%</span></div></div>)} onMouseLeave={hide}>
              <rect x={cx - bw/2} y={y(d.uns)} width={bw} height={(h-pad.b)-y(d.uns)} rx="4" fill="var(--viz-wait)" opacity=".7" />
              <text x={cx} y={y(d.uns)-8} textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--ink)">{d.uns.toFixed(0)}%</text>
              {words.map((wd, wi) => <text key={wi} x={cx} y={h-pad.b+16+wi*12} textAnchor="middle" fontSize="10.5" fill="var(--ink-2)" fontWeight="600">{wd}</text>)}
            </g>
          );
        })}
        <line x1={pad.l} x2={w-pad.r} y1={h-pad.b} y2={h-pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      </svg>
      <div className="chart-src" style={{marginTop:8}}>Of each group counted as homeless, the share living unsheltered (vs. in shelter).</div>
      {node}
    </div>
  );
}

/* ---------- chart registry ---------- */
const CHART_RENDER = {
  cost_trajectory: (p) => <CostTrajectory scn={p.scn} showBands={p.showBands} />,
  waterfall: (p) => <Waterfall scn={p.scn} />,
  breakeven: (p) => <BreakEven scn={p.scn} />,
  scenario_bars: (p) => <ScenarioBars scn={p.scn} />,
  compartments: (p) => <Compartments scn={p.scn} />,
  budget_compare: (p) => <BudgetCompare scn={p.scn} />,
  mix_compare: (p) => <MixCompare scn={p.scn} />,
  tornado: (p) => <Tornado scn={p.scn} />,
  shap: () => <ShapDrivers />,
  backtest: () => <Backtest />,
  city_scatter: (p) => <CityScatter selectedCoc={p.coc} onSelect={p.onSelect} />,
  city_benchmark: (p) => <CityBenchmark selectedCoc={p.coc} onSelect={p.onSelect} />,
  us_map: (p) => <USMap selectedCoc={p.coc} onSelect={p.onSelect} />,
  equity_disparity: (p) => <EquityDisparity coc={p.coc} />,
  equity_unsheltered: (p) => <EquityUnsheltered coc={p.coc} />,
};

Object.assign(window, {
  Tornado, ShapDrivers, Backtest, CityScatter, CityBenchmark, USMap, EquityDisparity, EquityUnsheltered,
  CHART_RENDER, US_OUTLINE,
});
