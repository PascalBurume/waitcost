/* ============================================================
   WaitCost — Ask screen (the hero)
   NL input → streamed agent thinking (tier badges, Tier-2 pause)
   → Direct Answer + recommended chart + trajectory + brief.
   States: idle · thinking · answer · declined · Tier-2 modal.
   ============================================================ */
var useState = React.useState, useEffect = React.useEffect, useRef = React.useRef, useMemo = React.useMemo;

function TierBadge({ tier }) {
  const label = tier === 2 ? "Tier 2 · human approval" : tier === 1 ? "Tier 1 · analysis" : "Tier 0 · read-only";
  return <span className={`tier tier-${tier}`}>{tier === 2 ? "⚑ " : ""}{label}</span>;
}

function Icon({ name, size = 16 }) {
  const p = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
  const paths = {
    spark: <><path d="M12 3v4M12 17v4M5 12H1M23 12h-4M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/></>,
    check: <polyline points="20 6 9 17 4 12"/>,
    chevron: <polyline points="6 9 12 15 18 9"/>,
    doc: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>,
    info: <><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></>,
    arrow: <><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>,
    stop: <><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></>,
    loader: <><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.9" y1="4.9" x2="7.8" y2="7.8"/><line x1="16.2" y1="16.2" x2="19.1" y2="19.1"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/></>,
  };
  return <svg {...p}>{paths[name]}</svg>;
}

/* classify a typed question into an intent */
function classify(q) {
  const s = q.toLowerCase();
  if (/(which|who).*(resident|person|people|individual|name|address|household)|predict.*(who|individual|person)|profile|street|block|neighborhood/.test(s))
    return "declined";
  if (/allocat|how should i (spend|split|divide)|recommend.*(budget|allocation|split)|where should.*(money|dollars|funds)/.test(s))
    return "allocate";
  if (/equity|over-?represent|disparit|race|racial|black|indigenous|native|who bears|who is affected|disproportion/.test(s))
    return "equity";
  return "scenario";
}

const SUGGESTED = [
  { q: "What does waiting 3 years to fund a $15M/yr program cost us?", intent: "scenario" },
  { q: "Who is over-represented among people experiencing homelessness here?", intent: "equity" },
  { q: "How should I allocate next year's $15M across interventions?", intent: "allocate" },
  { q: "Predict which residents will become homeless next year", intent: "declined" },
];

function stepsFor(intent, city) {
  const base = [
    { id: "understand", tier: 0, label: "Understanding the question", detail: `Parsed a budget-timing tradeoff for ${city.name}. No individual-level request.` },
    { id: "context", tier: 0, tool: "context_lookup", label: "Pulling local context", detail: `${WC.fmtNum(city.homeless)} in 2024 PIT · median home $${(city.home/1000).toFixed(0)}k · poverty ${city.pov}%.` },
  ];
  if (intent === "equity") {
    return [...base,
      { id: "equity", tier: 1, tool: "equity_query", label: "Computing population-level disparity", detail: "Group share of homeless ÷ group share of residents. No individuals." },
      { id: "explain", tier: 1, tool: "explain_brief", label: "Explaining with sources & ranges", detail: "Drafting a plain-English brief." },
    ];
  }
  const steps = [...base,
    { id: "scenario", tier: 1, tool: "scenario_montecarlo", label: "Running 3 scenarios (Monte-Carlo)", detail: "2,000 draws over a 10-year horizon: status quo, act now, delay." },
    { id: "backtest", tier: 0, tool: "backtest", label: "Backtesting against observed 2024", detail: `Predicted band contained the observed count (${WC.BACKTEST.errPct}% error).` },
  ];
  if (intent === "allocate") {
    steps.push({ id: "allocate", tier: 2, tool: "allocate_recommendation", label: "Recommending a specific allocation", detail: "This proposes how to split real dollars — it needs your sign-off." });
  }
  steps.push({ id: "explain", tier: 1, tool: "explain_brief", label: "Explaining with sources & ranges", detail: "Drafting a one-page decision brief." });
  return steps;
}

function StepItem({ step, status }) {
  return (
    <div className="step-item" data-status={status}>
      <div className="step-rail">
        <span className={"step-dot " + status}>
          {status === "done" ? <Icon name="check" size={13} /> : status === "running" ? <span className="spin"><Icon name="loader" size={13} /></span> : status === "blocked" ? <Icon name="shield" size={13} /> : null}
        </span>
      </div>
      <div className="step-body">
        <div className="step-head">
          <span className="step-label">{step.label}</span>
          <TierBadge tier={step.tier} />
          {step.tool && <span className="step-tool">{step.tool}()</span>}
        </div>
        {(status === "running" || status === "done" || status === "blocked") && <div className="step-detail">{step.detail}</div>}
      </div>
    </div>
  );
}

function AskScreen({ city, scn, onSeeChart, showBands }) {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [intent, setIntent] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | thinking | answer | declined
  const [steps, setSteps] = useState([]);
  const [active, setActive] = useState(-1);     // currently running step index
  const [blockedAt, setBlockedAt] = useState(-1); // tier-2 pause index
  const [approved, setApproved] = useState(false);
  const timer = useRef(null);

  function run(q, forcedIntent) {
    const it = forcedIntent || classify(q);
    setSubmitted(q); setIntent(it); setApproved(false); setBlockedAt(-1);
    if (it === "declined") { setPhase("declined"); setSteps([]); setActive(-1); return; }
    const st = stepsFor(it, city);
    setSteps(st); setPhase("thinking"); setActive(0);
  }

  // drive the streamed steps
  useEffect(() => {
    if (phase !== "thinking" || active < 0 || active >= steps.length) return;
    const cur = steps[active];
    if (cur.tier === 2 && !approved) { setBlockedAt(active); return; } // pause for approval
    const dwell = cur.tier === 1 ? 1150 : 700;
    timer.current = setTimeout(() => {
      if (active + 1 >= steps.length) { setActive(steps.length); setPhase("answer"); }
      else setActive(active + 1);
    }, dwell);
    return () => clearTimeout(timer.current);
  }, [phase, active, approved, steps]);

  function approve() { setApproved(true); setBlockedAt(-1); /* effect re-runs on `approved` and resumes the blocked step */ }

  function statusOf(i) {
    if (i === blockedAt && !approved) return "blocked";
    if (i < active) return "done";
    if (i === active && phase === "thinking") return "running";
    if (phase === "answer") return "done";
    return "pending";
  }

  const reset = () => { setPhase("idle"); setSubmitted(""); setSteps([]); setActive(-1); setBlockedAt(-1); setApproved(false); setQuery(""); };

  return (
    <div className="page">
      {phase === "idle" && (
        <div className="ask-hero rise">
          <div className="eyebrow" style={{ color: "var(--accent-ink)" }}>The cost of doing nothing</div>
          <h1 className="ask-h1 serif">What will the delay cost us?</h1>
          <p className="lede" style={{ maxWidth: 620, margin: "12px auto 0" }}>
            Ask in plain language about waiting, budgets, and who is affected. WaitCost runs real scenarios on
            government data, shows its uncertainty, and explains itself — for {city.name}.
          </p>
          <AskInput value={query} setValue={setQuery} onSubmit={() => query.trim() && run(query)} />
          <div className="suggested">
            {SUGGESTED.map((s, i) => (
              <button key={i} className="suggest-chip" onClick={() => { setQuery(s.q); run(s.q, s.intent); }}>
                {s.intent === "declined" && <Icon name="stop" size={14} />}
                {s.intent === "allocate" && <Icon name="shield" size={14} />}
                {s.q}
              </button>
            ))}
          </div>
          <div className="ask-facts">
            <span><b>17</b> CoC cities</span><span className="sep">·</span>
            <span><b>2</b> AI agents</span><span className="sep">·</span>
            <span><b>15</b> decision charts</span><span className="sep">·</span>
            <span>runs fully offline</span>
          </div>
        </div>
      )}

      {phase !== "idle" && (
        <div className="ask-result">
          <div className="ask-query-bar">
            <button className="btn-quiet" onClick={reset} aria-label="New question"><Icon name="arrow" size={16} style={{ transform: "rotate(180deg)" }} /></button>
            <div className="ask-query-text">{submitted}</div>
            <button className="btn-ghost btn-sm" onClick={reset}>Ask another</button>
          </div>

          {/* thinking / trajectory */}
          {(phase === "thinking" || phase === "answer") && (
            <div className="card thinking-card">
              <div className="thinking-head">
                <span className="row gap-8" style={{ alignItems: "center" }}>
                  <span className="agent-glow"><Icon name="spark" size={15} /></span>
                  <b>{phase === "thinking" ? "Analyst agent — working" : "Agent trajectory"}</b>
                </span>
                {phase === "answer" && <span className="pill">{steps.length} steps · {steps.filter(s=>s.tool).length} tool calls</span>}
              </div>
              <div className="steps">
                {steps.map((s, i) => <StepItem key={s.id} step={s} status={statusOf(i)} />)}
              </div>
            </div>
          )}

          {/* answer */}
          {phase === "answer" && intent !== "equity" && <ScenarioAnswer scn={scn} onSeeChart={onSeeChart} showBands={showBands} allocate={intent === "allocate"} />}
          {phase === "answer" && intent === "equity" && <EquityAnswer city={city} onSeeChart={onSeeChart} />}
        </div>
      )}

      {phase === "declined" && <DeclinedCard query={submitted} onReset={reset} />}

      {/* Tier-2 approval modal */}
      {blockedAt >= 0 && !approved && (
        <ApprovalModal step={steps[blockedAt]} city={city} onApprove={approve} onCancel={() => { setPhase("answer"); setBlockedAt(-1); setActive(steps.length); }} />
      )}
    </div>
  );
}

function AskInput({ value, setValue, onSubmit }) {
  return (
    <form className="ask-input" onSubmit={e => { e.preventDefault(); onSubmit(); }}>
      <span className="ask-input-ico"><Icon name="spark" size={18} /></span>
      <input autoFocus value={value} onChange={e => setValue(e.target.value)}
        placeholder="Ask about waiting, budgets, who's affected…" aria-label="Ask WaitCost a question" />
      <button type="submit" className="btn btn-primary btn-sm" disabled={!value.trim()}>Ask<Icon name="arrow" size={15} /></button>
    </form>
  );
}

function ScenarioAnswer({ scn, onSeeChart, showBands, allocate }) {
  const [open, setOpen] = useState(true);
  const cow = WC.fmtMoney(scn.costOfWaiting);
  return (
    <div className="answer-stack">
      <div className="card answer-card rise">
        <div className="answer-eyebrow"><span className="eyebrow">Direct answer</span><span className="pill">80% range shown</span></div>
        <div className="answer-headline">
          <div className="answer-num tnum">{cow}<span className="answer-num-sub"> more over 10 years</span></div>
          <div className="range answer-range tnum">80% range <span className="br">·</span> {WC.fmtMoney(scn.costOfWaitingLo)} – {WC.fmtMoney(scn.costOfWaitingHi)}</div>
        </div>
        <p className="answer-sentence serif">
          Waiting <b>{scn.delay} years</b> to fund a <b>${scn.budget}M/yr</b> program is projected to cost <b>{scn.city.name}</b> about <b>{cow} more</b> over
          ten years than acting now. Acting now is estimated to save <b>{WC.fmtMoney(scn.actNowSaves)}</b> versus the status quo
          (10-year public cost ≈ <b>{WC.fmtMoney(scn.statusQuo10)}</b>, range {WC.fmtMoney(scn.statusQuo10Lo)}–{WC.fmtMoney(scn.statusQuo10Hi)}).
        </p>
        {allocate && <div className="approved-note"><Icon name="check" size={14} /> Allocation recommendation approved and signed off — included in the brief below.</div>}
      </div>

      <div className="card chart-card rise">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 14, alignItems: "baseline" }}>
          <div><div className="chart-title">The cost of waiting, year by year</div><div className="muted" style={{ fontSize: "var(--fs-sm)" }}>Cumulative extra public cost vs. acting now · recommended chart</div></div>
          <button className="btn-ghost btn-sm" onClick={() => onSeeChart("cost_trajectory")}>Open in Visualize</button>
        </div>
        <CostTrajectory scn={scn} showBands={showBands} />
        <div className="chart-src"><Icon name="info" size={13} /> Source: HUD 2024 PIT · Census ACS 2024 · scenario_montecarlo (2,000 draws). All values are ranges.</div>
      </div>

      <DecisionBrief scn={scn} open={open} setOpen={setOpen} allocate={allocate} />
    </div>
  );
}

function DecisionBrief({ scn, open, setOpen, allocate }) {
  return (
    <div className="card brief-card rise">
      <button className="brief-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="row gap-8" style={{ alignItems: "center" }}><Icon name="doc" size={16} /><b>Decision brief</b><span className="muted">one-page memo</span></span>
        <span style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }}><Icon name="chevron" size={18} /></span>
      </button>
      {open && (
        <div className="brief-body serif fade">
          <div className="brief-memo-head">
            <div><span className="brief-to">MEMO · Budget-timing analysis</span><h3 className="brief-title">The cost of waiting on homelessness funding — {scn.city.name}</h3></div>
            <div className="brief-meta tnum">CoC {scn.city.coc}<br/>{WC.VINTAGE}</div>
          </div>
          <p><b>Question.</b> If we delay funding a ${scn.budget}M/yr intervention by {scn.delay} years, what does the delay cost over a ten-year horizon?</p>
          <p><b>Finding.</b> The delay is projected to add about <b>{WC.fmtMoney(scn.costOfWaiting)}</b> in public cost over ten years (80% range {WC.fmtMoney(scn.costOfWaitingLo)}–{WC.fmtMoney(scn.costOfWaitingHi)}). The status-quo ten-year public cost is on the order of {WC.fmtMoney(scn.statusQuo10)} ({WC.fmtMoney(scn.statusQuo10Lo)}–{WC.fmtMoney(scn.statusQuo10Hi)}). Acting now is estimated to save {WC.fmtMoney(scn.actNowSaves)} relative to doing nothing.</p>
          <p><b>Why.</b> Each year of delay forgoes the avoided costs an active program would have begun accruing — emergency services, health care, and justice-system contact concentrated among unsheltered residents. The benefit ramps in over roughly {scn.tau.toFixed(1)} years, so early years of delay are the most expensive to give up.</p>
          <p><b>Uncertainty.</b> The single largest driver of the range is the intervention-effect assumption, which is low-confidence; under ±50% on that term the headline spans {WC.fmtMoney(scn.costOfWaiting*0.55)}–{WC.fmtMoney(scn.costOfWaiting*1.5)}. Figures are modeled ranges, not forecasts of individuals.</p>
          <p><b>Equity note.</b> Costs and harms are not evenly distributed; population-level disproportionality is summarized on the Equity tab. This analysis never profiles individuals.</p>
          <p><b>{allocate ? "Recommendation (human-approved)." : "What this informs."}</b> {allocate
            ? `With sign-off, a balanced split — roughly 34% prevention, 33% rapid-rehousing, 33% supportive housing — maximizes modeled savings at this budget. This is a recommendation, not an allocation; the final decision remains with the budget director.`
            : `This memo informs a budget-timing tradeoff. It does not decide allocations or forecast individuals.`}</p>
          <div className="brief-sources">
            <span className="eyebrow">Sources</span>
            <ul><li>HUD 2024 Point-in-Time count (CoC {scn.city.coc})</li><li>U.S. Census ACS 2024 (population, poverty, median home value)</li><li>WaitCost scenario_montecarlo · backtest · explain_brief</li></ul>
          </div>
        </div>
      )}
    </div>
  );
}

function EquityAnswer({ city, onSeeChart }) {
  const eq = WC.equityFor(city.coc);
  const top = [...eq.groups].sort((a,b)=>b.disp-a.disp)[0];
  return (
    <div className="answer-stack">
      <div className="card answer-card rise">
        <div className="answer-eyebrow"><span className="eyebrow">Direct answer</span><span className="pill">Population-level only</span></div>
        <div className="answer-headline">
          <div className="answer-num tnum">{top.disp.toFixed(1)}×<span className="answer-num-sub"> over-represented</span></div>
        </div>
        <p className="answer-sentence serif">
          In {city.name}, <b>{top.g}</b> residents are counted among people experiencing homelessness at about <b>{top.disp.toFixed(1)}×</b> their
          share of the population — the largest disparity here. This is a population-level ratio. WaitCost never profiles individuals.
        </p>
      </div>
      <div className="card chart-card rise">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 14, alignItems: "baseline" }}>
          <div><div className="chart-title">Over-representation by group</div><div className="muted" style={{ fontSize: "var(--fs-sm)" }}>Recommended chart · auto-selected</div></div>
          <button className="btn-ghost btn-sm" onClick={() => onSeeChart("equity_disparity")}>Open in Visualize</button>
        </div>
        <EquityDisparity coc={city.coc} />
        <div className="chart-src"><Icon name="info" size={13} /> Source: HUD 2024 PIT demographics · Census ACS 2024 population shares.</div>
      </div>
    </div>
  );
}

function DeclinedCard({ query, onReset }) {
  return (
    <div className="declined-wrap rise">
      <div className="card declined-card">
        <span className="declined-ico"><Icon name="shield" size={22} /></span>
        <h2 className="declined-h">I can't answer that one</h2>
        <p className="declined-body serif">
          I work at the <b>city level</b> and don't profile individuals. I can't predict, identify, or rank specific
          residents, households, neighborhoods, or blocks — by design, and to protect people.
        </p>
        <div className="declined-q">You asked: <span className="serif">“{query}”</span></div>
        <p className="declined-alt">Here's what I <i>can</i> help with instead:</p>
        <div className="declined-suggest">
          {SUGGESTED.filter(s => s.intent !== "declined").map((s, i) => (
            <button key={i} className="suggest-chip" onClick={onReset}>{s.q}</button>
          ))}
        </div>
        <button className="btn btn-ghost" style={{ marginTop: 18 }} onClick={onReset}>Ask a different question</button>
      </div>
    </div>
  );
}

function ApprovalModal({ step, city, onApprove, onCancel }) {
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    const onKey = e => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="overlay fade" onMouseDown={e => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="modal approval-modal rise" role="dialog" aria-modal="true" aria-labelledby="appr-title">
        <div className="approval-head">
          <span className="tier tier-2">⚑ Tier 2 · human approval</span>
        </div>
        <h2 id="appr-title" className="approval-title">Recommending a specific allocation needs your sign-off</h2>
        <p className="approval-body">
          The analyst agent is ready to propose how to split <b>real dollars</b> across prevention, rapid-rehousing, and
          supportive housing for <b>{city.name}</b>. Recommendations that touch budget actions pause here — a person,
          not the model, decides.
        </p>
        <div className="approval-detail">
          <div className="row gap-8" style={{ marginBottom: 6 }}><span className="step-tool">{step.tool}()</span><span className="muted" style={{ fontSize: "var(--fs-xs)" }}>read-write · logged</span></div>
          <div className="muted" style={{ fontSize: "var(--fs-sm)" }}>{step.detail}</div>
        </div>
        <label className="approval-check">
          <input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} />
          <span>I am the budget director (or delegate) and I approve generating this recommendation. It informs, and does not execute, any allocation.</span>
        </label>
        <div className="approval-actions">
          <button className="btn btn-ghost" onClick={onCancel}>Skip — answer without it</button>
          <button className="btn btn-primary" disabled={!checked} onClick={onApprove}>Approve & continue</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AskScreen, TierBadge, Icon, classify });
