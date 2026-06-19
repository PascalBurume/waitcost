/* ============================================================
   WaitCost — Explore · Visualize · Where's the AI · Equity
              · Governance · Map
   ============================================================ */
var useState = React.useState, useEffect = React.useEffect, useRef = React.useRef, useMemo = React.useMemo;

/* ---------- shared bits ---------- */
function StatTile({ label, value, sub, accent, big }) {
  return (
    <div className="stat-tile">
      <div className="stat-tile-label">{label}</div>
      <div className={"stat-tile-val tnum" + (big ? " big" : "")} style={accent ? { color: "var(--accent-ink)" } : null}>{value}</div>
      {sub && <div className="stat-tile-sub tnum">{sub}</div>}
    </div>
  );
}
function SrcLine({ children }) {
  return <div className="chart-src"><Icon name="info" size={13} /> {children}</div>;
}
function SectionHead({ kicker, title, desc }) {
  return (
    <div className="section-head">
      {kicker && <div className="eyebrow" style={{ color: "var(--accent-ink)" }}>{kicker}</div>}
      <h1 className="page-title serif">{title}</h1>
      {desc && <p className="lede" style={{ maxWidth: 720 }}>{desc}</p>}
    </div>
  );
}

/* =========================================================================
   EXPLORE
   ========================================================================= */
function ExploreScreen({ city, controls, setControls, showBands }) {
  const scn = useMemo(() => WC.computeScenario({
    city, budget: controls.budget, delay: controls.delay, mix: normMix(controls.mix),
  }), [city, controls]);

  function normMix(m) { const t = m.prev + m.rrh + m.psh || 1; return { prev: m.prev/t, rrh: m.rrh/t, psh: m.psh/t }; }
  const nm = normMix(controls.mix);

  return (
    <div className="page page-wide">
      <SectionHead kicker="Explore" title="Move the levers, watch the cost"
        desc={`Adjust the program for ${city.name}. Every line carries its P10–P90 uncertainty band — the honest spread, not a single guess.`} />
      <div className="explore-grid">
        <div className="card explore-controls">
          <Slider label="Annual budget" val={`$${controls.budget}M`} min={5} max={40} step={1} value={controls.budget}
            onChange={v => setControls({ ...controls, budget: v })} />
          <Slider label="Years of delay" val={controls.delay === 0 ? "Act now" : `${controls.delay} yr`} min={0} max={7} step={1} value={controls.delay}
            onChange={v => setControls({ ...controls, delay: v })} />
          <div className="mix-block">
            <div className="slider-label" style={{ marginBottom: 10 }}>Intervention mix</div>
            <MixSlider label="Prevention" pct={Math.round(nm.prev*100)} value={controls.mix.prev} onChange={v => setControls({ ...controls, mix: { ...controls.mix, prev: v } })} />
            <MixSlider label="Rapid-rehousing" pct={Math.round(nm.rrh*100)} value={controls.mix.rrh} onChange={v => setControls({ ...controls, mix: { ...controls.mix, rrh: v } })} />
            <MixSlider label="Supportive housing" pct={Math.round(nm.psh*100)} value={controls.mix.psh} onChange={v => setControls({ ...controls, mix: { ...controls.mix, psh: v } })} />
            <div className="mix-bar" aria-hidden="true">
              <span style={{ flex: nm.prev, background: "var(--viz-act)", opacity: .55 }}></span>
              <span style={{ flex: nm.rrh, background: "var(--viz-act)", opacity: .78 }}></span>
              <span style={{ flex: nm.psh, background: "var(--viz-act)" }}></span>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm reset-btn" onClick={() => setControls({ budget: 15, delay: 3, mix: { prev: 34, rrh: 33, psh: 33 } })}>Reset to baseline</button>
        </div>

        <div className="explore-main">
          <div className="kpi-row">
            <StatTile label={`Cost of waiting ${scn.delay}y`} value={WC.fmtMoney(scn.costOfWaiting)} sub={`${WC.fmtMoney(scn.costOfWaitingLo)} – ${WC.fmtMoney(scn.costOfWaitingHi)}`} accent big />
            <StatTile label="Acting now saves" value={WC.fmtMoney(scn.actNowSaves)} sub="vs. status quo, 10-yr" />
            <StatTile label="Break-even" value={scn.breakEvenYear ? `Year ${scn.breakEvenYear}` : "—"} sub="act-now overtakes delay" />
          </div>
          <div className="card chart-card">
            <div className="chart-title" style={{ marginBottom: 4 }}>The cost of waiting, year by year</div>
            <div className="muted" style={{ fontSize: "var(--fs-sm)", marginBottom: 12 }}>Do nothing · delay · act now — cumulative extra cost vs. acting now, with P10–P90 bands</div>
            <CostTrajectory scn={scn} showBands={showBands} animate={false} />
            <SrcLine>HUD 2024 PIT · Census ACS 2024 · scenario_montecarlo. Figures are modeled ranges.</SrcLine>
          </div>
          <div className="card sens-strip">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
              <div><b>Assumption sensitivity</b> <span className="muted" style={{ fontSize: "var(--fs-sm)" }}>honesty as a feature</span></div>
              <span className="tier tier-2" style={{ background: "var(--surface-2)" }}>low-confidence input</span>
            </div>
            <SensBar scn={scn} />
            <div className="muted" style={{ fontSize: "var(--fs-sm)", marginTop: 12 }}>
              Under ±50% on the (low-confidence) intervention-effect assumption, the headline cost of waiting ranges
              <b className="tnum"> {WC.fmtMoney(scn.costOfWaiting*0.55)} </b> to <b className="tnum">{WC.fmtMoney(scn.costOfWaiting*1.5)}</b>. We show the spread rather than hide it.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
function Slider({ label, val, min, max, step, value, onChange }) {
  return (
    <div className="slider-wrap">
      <div className="slider-row"><span className="slider-label">{label}</span><span className="slider-val">{val}</span></div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(+e.target.value)} aria-label={label} />
    </div>
  );
}
function MixSlider({ label, pct, value, onChange }) {
  return (
    <div className="mix-slider">
      <div className="slider-row"><span className="slider-sub">{label}</span><span className="slider-val tnum">{pct}%</span></div>
      <input type="range" min={0} max={100} step={1} value={value} onChange={e => onChange(+e.target.value)} aria-label={label + " share"} />
    </div>
  );
}
function SensBar({ scn }) {
  const lo = scn.costOfWaiting*0.55, hi = scn.costOfWaiting*1.5, base = scn.costOfWaiting;
  const x = v => ((v - lo) / (hi - lo)) * 100;
  return (
    <div className="sens-track">
      <div className="sens-fill" style={{ left: x(scn.costOfWaitingLo) + "%", width: (x(scn.costOfWaitingHi)-x(scn.costOfWaitingLo)) + "%" }}></div>
      <div className="sens-wide" style={{ left: "0%", width: "100%" }}></div>
      <div className="sens-marker" style={{ left: x(base) + "%" }}><span className="sens-flag tnum">{WC.fmtMoney(base)}</span></div>
      <div className="sens-end left tnum">{WC.fmtMoney(lo)}</div>
      <div className="sens-end right tnum">{WC.fmtMoney(hi)}</div>
    </div>
  );
}

/* =========================================================================
   VISUALIZE — gallery of 15 charts
   ========================================================================= */
function VisualizeScreen({ city, scn, selected, setSelected, onSelectCity, showBands }) {
  const groups = ["Decision", "Honesty", "Model", "Context", "Equity"];
  const cur = WC.CHARTS.find(c => c.id === selected) || WC.CHARTS[0];
  const render = CHART_RENDER[cur.id];
  return (
    <div className="page page-wide">
      <SectionHead kicker="Visualize" title="Fifteen ways to read the decision"
        desc="Pick a chart. Each renders large, in our visual system, with a caption and a source line. Built by the visualization agent." />
      <div className="viz-layout">
        <div className="viz-picker">
          {groups.map(g => (
            <div key={g} className="viz-group">
              <div className="viz-group-label">{g}</div>
              {WC.CHARTS.filter(c => c.group === g).map(c => (
                <button key={c.id} className={"viz-pick" + (c.id === selected ? " active" : "")} onClick={() => setSelected(c.id)}>
                  <span className="viz-pick-spark"><ChartGlyph id={c.id} /></span>
                  <span className="viz-pick-text"><span className="viz-pick-name">{c.name}{c.wow && <span className="wow-dot" title="Signature chart"></span>}</span><span className="viz-pick-desc">{c.desc}</span></span>
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="card viz-stage">
          <div className="viz-stage-head">
            <div><div className="eyebrow">{cur.group}</div><div className="chart-title">{cur.name}</div></div>
            <span className="pill">{city.name}</span>
          </div>
          <div className="viz-stage-body" key={selected}>
            {render ? render({ scn, coc: city.coc, onSelect: onSelectCity, showBands }) : null}
          </div>
          <p className="chart-cap">{cur.desc}</p>
          <SrcLine>HUD 2024 PIT · Census ACS 2024{cur.group === "Model" ? " · Ridge model (leave-one-CoC-out)" : ""}. All figures shown as ranges.</SrcLine>
        </div>
      </div>
    </div>
  );
}
function ChartGlyph({ id }) {
  // tiny iconographic preview per chart family
  const g = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" };
  const map = {
    bars: <><line x1="5" y1="20" x2="5" y2="12"/><line x1="12" y1="20" x2="12" y2="6"/><line x1="19" y1="20" x2="19" y2="14"/></>,
    line: <polyline points="3 17 9 11 13 14 21 5"/>,
    area: <><polyline points="3 16 9 10 13 13 21 6"/><path d="M3 16 9 10 13 13 21 6 21 21 3 21Z" fill="currentColor" opacity=".15" stroke="none"/></>,
    dot: <><line x1="4" y1="12" x2="20" y2="12"/><circle cx="14" cy="12" r="3" fill="currentColor"/></>,
    scatter: <><circle cx="6" cy="16" r="1.6"/><circle cx="11" cy="11" r="1.6"/><circle cx="16" cy="8" r="1.6"/><circle cx="19" cy="13" r="1.6"/></>,
    map: <path d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3Z"/>,
  };
  const family = { cost_trajectory:"line", waterfall:"bars", breakeven:"line", scenario_bars:"bars", compartments:"area",
    budget_compare:"bars", mix_compare:"bars", tornado:"bars", shap:"bars", backtest:"dot",
    city_scatter:"scatter", city_benchmark:"bars", us_map:"map", equity_disparity:"bars", equity_unsheltered:"bars" };
  return <svg {...g}>{map[family[id]] || map.bars}</svg>;
}

/* =========================================================================
   WHERE'S THE AI — model card
   ========================================================================= */
function ModelScreen({ city, onSelectCity }) {
  const m = WC.MODEL, bt = WC.BACKTEST;
  return (
    <div className="page page-wide">
      <SectionHead kicker="Where's the AI" title="Here's how the model works — and proof it matched reality"
        desc="A deliberately modest learned model, cross-checked against an official measure and replayed against a year it never saw." />
      <div className="model-tiles">
        <StatTile label="Held-out R² (leave-one-CoC-out)" value={m.r2.toFixed(2)} sub="honest out-of-sample fit" accent big />
        <StatTile label="Model vs HUD SPM monthly inflow" value={`${WC.fmtNum(m.predInflow)} / ${WC.fmtNum(m.spmInflow)}`} sub={`~${m.inflowGapPct}% apart`} />
        <StatTile label="Model type" value={m.type} sub={`trained across ${m.nCities} CoCs`} />
        <StatTile label="2024 backtest error" value={`${bt.errPct}%`} sub="observed inside predicted band" />
      </div>
      <div className="model-grid">
        <div className="card chart-card">
          <div className="chart-title" style={{ marginBottom: 4 }}>What the model leans on</div>
          <div className="muted" style={{ fontSize: "var(--fs-sm)", marginBottom: 14 }}>SHAP contributions — housing cost dominates</div>
          <ShapDrivers />
          <SrcLine>Ridge regression · SHAP attribution across {m.nCities} CoCs.</SrcLine>
        </div>
        <div className="card chart-card">
          <div className="chart-title" style={{ marginBottom: 4 }}>Did it match reality?</div>
          <div className="muted" style={{ fontSize: "var(--fs-sm)", marginBottom: 14 }}>Predicted 2024 band vs the observed PIT count</div>
          <Backtest />
        </div>
      </div>
      <div className="card chart-card" style={{ marginTop: 20 }}>
        <div className="chart-title" style={{ marginBottom: 4 }}>Where {city.name} sits</div>
        <div className="muted" style={{ fontSize: "var(--fs-sm)", marginBottom: 14 }}>Housing cost vs homelessness rate across 17 CoCs · click a point to switch city</div>
        <CityScatter selectedCoc={city.coc} onSelect={onSelectCity} />
        <SrcLine>Census ACS 2024 median home value · HUD 2024 PIT rate per 1,000.</SrcLine>
      </div>
    </div>
  );
}

/* =========================================================================
   EQUITY
   ========================================================================= */
function EquityScreen({ city }) {
  const eq = WC.equityFor(city.coc);
  const top = [...eq.groups].sort((a,b)=>b.disp-a.disp)[0];
  return (
    <div className="page page-wide">
      <SectionHead kicker="Equity" title="Who bears this"
        desc={`The cost of waiting does not fall evenly. These are population-level patterns for ${city.name} — a question of fairness, shown plainly.`} />
      <div className="equity-callout card">
        <span className="equity-callout-ico"><Icon name="shield" size={20} /></span>
        <div>
          <div className="equity-callout-h">Population-level only — this never profiles individuals.</div>
          <div className="equity-callout-b">Every figure is a group's share of an aggregate count, divided by its share of residents. No person, household, neighborhood, or block is ever identified or predicted.</div>
        </div>
      </div>
      <div className="equity-lead card">
        <div className="equity-lead-num tnum">{top.disp.toFixed(1)}×</div>
        <p className="serif">In {city.name}, <b>{top.g}</b> residents are over-represented among people experiencing homelessness by about <b>{top.disp.toFixed(1)} times</b> their share of the population — the widest gap here.{eq.estimated ? " (City profile estimated pending local demographic release.)" : ""}</p>
      </div>
      <div className="equity-grid">
        <div className="card chart-card">
          <div className="chart-title" style={{ marginBottom: 4 }}>Over-representation vs. population share</div>
          <div className="muted" style={{ fontSize: "var(--fs-sm)", marginBottom: 14 }}>Bars past the 1.0× parity line are over-represented</div>
          <EquityDisparity coc={city.coc} />
          <SrcLine>HUD 2024 PIT demographics ÷ Census ACS 2024 population shares.</SrcLine>
        </div>
        <div className="card chart-card">
          <div className="chart-title" style={{ marginBottom: 4 }}>Share living unsheltered, by group</div>
          <div className="muted" style={{ fontSize: "var(--fs-sm)", marginBottom: 14 }}>Of those counted as homeless, who is outside</div>
          <EquityUnsheltered coc={city.coc} />
          <SrcLine>HUD 2024 PIT sheltered/unsheltered status by group.</SrcLine>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   GOVERNANCE
   ========================================================================= */
function GovernanceScreen({ city }) {
  const [thin, setThin] = useState(false);
  return (
    <div className="page page-wide">
      <SectionHead kicker="Governance" title="Rules the agents run under"
        desc="What the AI is allowed to do on its own, where a human must sign off, and how it behaves when the data is too thin to be honest." />
      <div className="gov-grid">
        <div className="card gov-tiers">
          <div className="chart-title" style={{ marginBottom: 14 }}>Action tiers</div>
          <div className="tier-table">
            {WC.TIERS.map(t => (
              <div key={t.tier} className="tier-row">
                <div className={`tier tier-${t.tier}`}>{t.tier === 2 ? "⚑ " : ""}Tier {t.tier}</div>
                <div className="tier-cell"><div className="tier-cell-h">{t.label}</div><div className="tier-cell-d">{t.desc}</div></div>
                <div className="tier-gate">{t.gate}</div>
              </div>
            ))}
          </div>
          <div className="gov-tools">
            <div className="eyebrow" style={{ marginBottom: 8 }}>Tool registry</div>
            {WC.TOOLS.map(t => (
              <div key={t.id} className="gov-tool">
                <span className="step-tool">{t.name}()</span>
                <span className={`tier tier-${t.tier}`}>{t.tier === 2 ? "⚑ " : ""}T{t.tier}</span>
                <span className="gov-tool-desc">{t.desc}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="col gap-20">
          <div className="card gov-suff">
            <div className="chart-title" style={{ marginBottom: 4 }}>Data sufficiency</div>
            <div className="muted" style={{ fontSize: "var(--fs-sm)", marginBottom: 14 }}>What happens when the data is too thin? It declines rather than guessing.</div>
            <div className="seg" role="group" aria-label="Data condition" style={{ marginBottom: 16 }}>
              <button aria-pressed={!thin} onClick={() => setThin(false)}>Full data</button>
              <button aria-pressed={thin} onClick={() => setThin(true)}>Thin data</button>
            </div>
            {!thin ? (
              <div className="suff-ok fade">
                <span className="suff-badge ok"><Icon name="check" size={14} /> Sufficient</span>
                <p className="serif">{city.name} has {`${city.real ? "a complete" : "an adequate"}`} 2024 PIT record and ACS coverage. The agent runs the full scenario and returns an answer with ranges.</p>
              </div>
            ) : (
              <div className="suff-no fade">
                <span className="suff-badge no"><Icon name="stop" size={14} /> Declined — insufficient data</span>
                <p className="serif">Imagine the 2024 count is missing and only a partial 2019 record exists. Rather than extrapolate across five years and present false precision, the agent declines:</p>
                <div className="suff-quote serif">“I don't have recent enough data for {city.name} to answer this honestly. A scenario here would be guessing. I'd rather tell you that than show you a confident wrong number.”</div>
              </div>
            )}
          </div>
          <div className="card gov-sources">
            <div className="chart-title" style={{ marginBottom: 12 }}>Data sources & lifecycle</div>
            <ul className="src-list">
              <li><b>HUD 2024 Point-in-Time (PIT) count</b> — sheltered & unsheltered totals, chronic status, demographics, per CoC.</li>
              <li><b>U.S. Census ACS 2024</b> — population, poverty rate, median home value, rent burden.</li>
              <li><b>HUD System Performance Measures</b> — inflow cross-check.</li>
            </ul>
            <div className="lifecycle">
              <div className="eyebrow" style={{ marginBottom: 6 }}>Recalibration</div>
              <p className="muted" style={{ fontSize: "var(--fs-sm)" }}>The model is retrained when each annual PIT release lands and re-backtested on the newest held-out year before any answer changes. Ranges widen automatically as data ages.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   MAP
   ========================================================================= */
function MapScreen({ city, scn, onSelectCity }) {
  return (
    <div className="page page-wide">
      <SectionHead kicker="Map" title="Seventeen cities, one question each"
        desc="Bubbles are sized by homelessness rate per 1,000 residents. Click any city to re-skin every screen to it." />
      <div className="map-layout">
        <div className="card map-stage">
          <USMap selectedCoc={city.coc} onSelect={onSelectCity} />
          <SrcLine>HUD 2024 PIT counts ÷ Census ACS 2024 population. Bubble area ∝ rate per 1,000.</SrcLine>
        </div>
        <div className="card map-panel">
          <div className="map-panel-eyebrow"><span className="eyebrow">Selected city</span>{city.real ? <span className="pill">measured</span> : <span className="pill">estimated profile</span>}</div>
          <h2 className="map-city serif">{city.name}</h2>
          <div className="map-coc tnum">CoC {city.coc} · {city.st}</div>
          <div className="map-stats">
            <StatTile label="People homeless (2024 PIT)" value={WC.fmtNum(city.homeless)} sub={`${WC.fmtNum(city.unsheltered)} unsheltered · ${WC.fmtNum(city.sheltered)} sheltered`} big />
            <StatTile label="Rate per 1,000 residents" value={city.rate} accent />
            <StatTile label="Chronically homeless" value={WC.fmtNum(city.chronic)} />
            <StatTile label="Median home value" value={`$${(city.home/1000).toFixed(0)}k`} sub={`poverty ${city.pov}%`} />
          </div>
          <div className="map-cow">
            <div className="map-cow-label">Cost of waiting 3 yrs · $15M/yr program</div>
            <div className="map-cow-num tnum">{WC.fmtMoney(scn.costOfWaiting)}</div>
            <div className="range tnum">80% range · {WC.fmtMoney(scn.costOfWaitingLo)} – {WC.fmtMoney(scn.costOfWaitingHi)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  ExploreScreen, VisualizeScreen, ModelScreen, EquityScreen, GovernanceScreen, MapScreen,
  StatTile, SectionHead, SrcLine,
});
