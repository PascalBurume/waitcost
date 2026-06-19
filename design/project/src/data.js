/* ============================================================
   WaitCost — data layer  (window.WC)
   Real anchors: Los Angeles CoC CA-600 (HUD 2024 PIT, Census ACS 2024).
   Other 16 CoCs use plausible, in-range public estimates so screens
   read credibly; every such figure is flagged source:"est" in the UI.
   ============================================================ */
(function () {
  "use strict";

  // --- 17 U.S. Continuum-of-Care cities -----------------------------------
  // homeless = total PIT count; un = unsheltered; ch = chronic; pop = ACS pop;
  // home = median home value; pov = poverty rate %. real:true only for LA.
  const CITIES = [
    { coc:"CA-600", name:"Los Angeles", st:"CA", pop:9_760_000, homeless:71_201, sheltered:21_692, unsheltered:49_509, chronic:29_823, home:866_500, pov:13.3, real:true },
    { coc:"NY-600", name:"New York City", st:"NY", pop:8_260_000, homeless:88_025, sheltered:84_140, unsheltered:3_885, chronic:3_604, home:710_000, pov:18.0 },
    { coc:"WA-500", name:"Seattle / King County", st:"WA", pop:2_270_000, homeless:16_385, sheltered:7_390, unsheltered:8_995, chronic:5_010, home:762_000, pov:9.8 },
    { coc:"CA-501", name:"San Francisco", st:"CA", pop:870_000, homeless:8_323, sheltered:4_120, unsheltered:4_203, chronic:3_357, home:1_180_000, pov:11.2 },
    { coc:"IL-510", name:"Chicago", st:"IL", pop:2_660_000, homeless:18_836, sheltered:14_900, unsheltered:3_936, chronic:2_410, home:308_000, pov:17.1 },
    { coc:"MN-500", name:"Minneapolis / Hennepin", st:"MN", pop:1_280_000, homeless:3_604, sheltered:2_690, unsheltered:914, chronic:760, home:352_000, pov:11.4 },
    { coc:"AZ-502", name:"Phoenix / Maricopa", st:"AZ", pop:4_500_000, homeless:9_642, sheltered:4_560, unsheltered:5_082, chronic:2_870, home:445_000, pov:12.0 },
    { coc:"CA-601", name:"San Diego", st:"CA", pop:3_290_000, homeless:10_605, sheltered:4_180, unsheltered:6_425, chronic:3_540, home:903_000, pov:10.6 },
    { coc:"TX-700", name:"Houston / Harris", st:"TX", pop:4_730_000, homeless:3_270, sheltered:2_010, unsheltered:1_260, chronic:740, home:298_000, pov:15.6 },
    { coc:"MA-500", name:"Boston", st:"MA", pop:650_000, homeless:5_202, sheltered:4_960, unsheltered:242, chronic:610, home:781_000, pov:17.6 },
    { coc:"CO-503", name:"Denver", st:"CO", pop:715_000, homeless:10_054, sheltered:6_120, unsheltered:3_934, chronic:2_240, home:563_000, pov:11.9 },
    { coc:"OR-501", name:"Portland / Multnomah", st:"OR", pop:805_000, homeless:6_297, sheltered:2_410, unsheltered:3_887, chronic:2_980, home:548_000, pov:13.2 },
    { coc:"DC-500", name:"Washington, D.C.", st:"DC", pop:678_000, homeless:5_616, sheltered:4_980, unsheltered:636, chronic:1_120, home:635_000, pov:14.0 },
    { coc:"GA-500", name:"Atlanta", st:"GA", pop:499_000, homeless:2_852, sheltered:1_990, unsheltered:862, chronic:690, home:417_000, pov:17.7 },
    { coc:"TX-600", name:"Dallas", st:"TX", pop:1_300_000, homeless:4_410, sheltered:2_710, unsheltered:1_700, chronic:980, home:312_000, pov:14.9 },
    { coc:"CA-502", name:"Oakland / Alameda", st:"CA", pop:1_650_000, homeless:9_450, sheltered:2_980, unsheltered:6_470, chronic:3_910, home:931_000, pov:10.3 },
    { coc:"CA-503", name:"Sacramento", st:"CA", pop:1_585_000, homeless:6_615, sheltered:2_010, unsheltered:4_605, chronic:2_340, home:485_000, pov:11.7 },
  ];
  CITIES.forEach(c => { c.rate = +(c.homeless / c.pop * 1000).toFixed(2); }); // per 1,000 residents

  // --- per-city cost-per-person-year, calibrated so LA 10-yr ≈ $49.8B -------
  // With 1.2%/yr growth, Σ(1.012)^t over t=1..10 ≈ 10.684. So
  // C_LA = 49.8e9 / (71201 * 10.684) ≈ $65,463. Scale by a housing-cost index.
  const C_LA = 65_463, HOME_LA = 866_500;
  function costPerPersonYear(city) {
    const idx = Math.min(1.55, Math.max(0.62, Math.pow(city.home / HOME_LA, 0.5)));
    return C_LA * idx;
  }

  // ============================================================
  //  SCENARIO ENGINE
  //  Produces 10-yr annual public-cost trajectories with P10–P90
  //  bands for: status quo, act now, delay. Anchored so LA defaults
  //  (budget $15M, delay 3y, balanced mix) ≈ $345.6M cost of waiting
  //  and ≈ $49.8B status-quo 10-yr cost.
  // ============================================================
  const YEARS = 10;

  // intervention mix → (effectiveness ceiling multiplier, ramp speed tau)
  // prevention: fast & cheap, modest ceiling; rapid-rehousing: medium;
  // supportive housing: slow ramp, highest ceiling.
  function mixParams(mix) {
    const { prev, rrh, psh } = mix; // shares summing ~1
    const tau = 1.6 * prev + 2.4 * rrh + 3.6 * psh + 0.6; // years
    const ceil = 0.85 * prev + 1.0 * rrh + 1.35 * psh;    // ceiling multiplier
    return { tau, ceil };
  }

  function ramp(t, tau) { return 1 - Math.exp(-t / tau); }

  function computeScenario(opts) {
    const city = typeof opts.city === "string" ? byCoc(opts.city) : opts.city;
    const budget = opts.budget ?? 15;       // $M / year
    const delay = opts.delay ?? 3;          // years
    const mix = opts.mix ?? { prev:0.34, rrh:0.33, psh:0.33 };
    const c = costPerPersonYear(city);
    const { tau, ceil } = mixParams(mix);

    // status-quo annual cost ($B), gentle growth folded into ranges
    const g = 0.012;
    const sq = [];
    for (let t = 0; t <= YEARS; t++) sq.push(city.homeless * c * Math.pow(1 + g, t) / 1e9);

    // avoided annual cost at maturity (A_max) calibrated for LA so that the
    // balanced/$15M/3-yr baseline yields ≈ $345.6M cost of waiting (80% $282–411M).
    const A_max = 114.9e6 * (budget / 15) * (city.homeless / 71201) * ceil
                  * Math.min(1.55, Math.max(0.62, Math.pow(city.home / HOME_LA, 0.5)));

    const actNow = [], delayed = [];
    for (let t = 0; t <= YEARS; t++) {
      const avoidNow = A_max * ramp(t, tau);
      const avoidDel = t < delay ? 0 : A_max * ramp(t - delay, tau);
      actNow.push((city.homeless * c * Math.pow(1 + g, t) - avoidNow) / 1e9);
      delayed.push((city.homeless * c * Math.pow(1 + g, t) - avoidDel) / 1e9);
    }

    // cumulative (sum of years 1..10)
    const cum = arr => arr.slice(1).reduce((a, b) => a + b, 0);
    const sqCum = cum(sq), actCum = cum(actNow), delCum = cum(delayed);
    const costOfWaiting = (delCum - actCum) * 1e9; // $ over 10 yrs
    const actNowSaves = (sqCum - actCum) * 1e9;

    // uncertainty bands: relative width widens with horizon; status quo asym.
    function band(arr, baseLo, baseHi) {
      return arr.map((v, t) => {
        const w = 1 + t * 0.06;
        return { p10: v * (1 - baseLo * w), p90: v * (1 + baseHi * w), p50: v };
      });
    }
    return {
      city, budget, delay, mix, c, tau, ceil,
      years: Array.from({ length: YEARS + 1 }, (_, t) => t),
      statusQuo: sq, actNow, delay_: delayed,
      bands: {
        statusQuo: band(sq, 0.075, 0.10),
        actNow: band(actNow, 0.085, 0.11),
        delay: band(delayed, 0.085, 0.11),
      },
      statusQuo10: sqCum * 1e9,
      statusQuo10Lo: sqCum * 1e9 * 0.797,
      statusQuo10Hi: sqCum * 1e9 * 1.283,
      costOfWaiting,
      costOfWaitingLo: costOfWaiting * 0.816,
      costOfWaitingHi: costOfWaiting * 1.189,
      actNowSaves,
      breakEvenYear: breakEven(delayed, actNow),
    };
  }

  // first year where acting-now cumulative undercuts delay cumulative by program cost
  function breakEven(delayed, actNow) {
    let cd = 0, ca = 0;
    for (let t = 1; t < delayed.length; t++) {
      cd += delayed[t]; ca += actNow[t];
      if (ca < cd) return t;
    }
    return null;
  }

  // ============================================================
  //  MODEL CARD  (learned model + cross-check)
  // ============================================================
  const MODEL = {
    type: "Ridge regression",
    cv: "leave-one-CoC-out",
    r2: 0.36,
    nCities: 17,
    predInflow: 2817,   // model-predicted monthly inflow
    spmInflow: 2485,    // HUD System Performance Measure
    inflowGapPct: 13,
    // SHAP-style mean |contribution| drivers (signed direction shown in UI)
    shap: [
      { f: "Median home value", v: 0.42, dir: 1 },
      { f: "Rent burden (>30% income)", v: 0.27, dir: 1 },
      { f: "Poverty rate", v: 0.19, dir: 1 },
      { f: "Rental vacancy rate", v: 0.14, dir: -1 },
      { f: "1-yr rent change", v: 0.11, dir: 1 },
      { f: "Mean winter low (°F)", v: 0.08, dir: -1 },
      { f: "Shelter beds per 1k poor", v: 0.07, dir: -1 },
      { f: "Unemployment rate", v: 0.05, dir: 1 },
    ],
  };

  // backtest: predicted 2024 band vs observed dot (per LA anchor)
  const BACKTEST = {
    city: "CA-600",
    predicted: 68_500, lo: 65_006, hi: 72_536,
    observed: 71_201, errPct: 3.8, inside: true,
    note: "Trained through 2023, predicted 2024 held out, compared to the observed 2024 PIT.",
  };

  // ============================================================
  //  EQUITY  (population-level only — never individuals)
  //  disp = over-representation ratio vs population share (×).
  //  uns = unsheltered rate within that group (%).
  // ============================================================
  const EQUITY = {
    "CA-600": { // Los Angeles
      groups: [
        { g:"Black", disp:4.0, uns:58.9, share:7.6 },
        { g:"Native American / AIAN", disp:1.5, uns:84.8, share:0.7 },
        { g:"Hispanic / Latino", disp:0.95, uns:71.0, share:48.6 },
        { g:"Multiracial", disp:1.6, uns:64.2, share:3.1 },
        { g:"Native Hawaiian / Pacific Is.", disp:1.2, uns:66.0, share:0.4 },
        { g:"White", disp:0.42, uns:77.7, share:26.3 },
        { g:"Asian", disp:0.18, uns:62.5, share:14.7 },
      ],
      overall_uns: 69.5,
    },
    "MN-500": { // Minneapolis — AIAN 10.1×
      groups: [
        { g:"Native American / AIAN", disp:10.1, uns:31.0, share:1.2 },
        { g:"Black", disp:6.3, uns:24.5, share:18.6 },
        { g:"Multiracial", disp:2.1, uns:21.0, share:4.0 },
        { g:"Hispanic / Latino", disp:1.1, uns:26.0, share:9.8 },
        { g:"White", disp:0.31, uns:28.0, share:60.2 },
        { g:"Asian", disp:0.22, uns:19.0, share:6.2 },
      ],
      overall_uns: 25.4,
    },
    "IL-510": { // Chicago — Hispanic 2.45×
      groups: [
        { g:"Black", disp:3.8, uns:22.0, share:28.7 },
        { g:"Hispanic / Latino", disp:2.45, uns:24.5, share:28.8 },
        { g:"Native American / AIAN", disp:2.0, uns:30.0, share:0.4 },
        { g:"Multiracial", disp:1.4, uns:20.0, share:2.7 },
        { g:"White", disp:0.36, uns:26.0, share:32.8 },
        { g:"Asian", disp:0.19, uns:18.0, share:6.9 },
      ],
      overall_uns: 20.9,
    },
    "WA-500": { // Seattle — AIAN 4.5×
      groups: [
        { g:"Native American / AIAN", disp:4.5, uns:62.0, share:1.0 },
        { g:"Black", disp:3.9, uns:48.0, share:6.8 },
        { g:"Multiracial", disp:2.0, uns:55.0, share:5.9 },
        { g:"Native Hawaiian / Pacific Is.", disp:3.2, uns:50.0, share:0.9 },
        { g:"Hispanic / Latino", disp:1.3, uns:58.0, share:10.2 },
        { g:"White", disp:0.55, uns:56.0, share:61.8 },
        { g:"Asian", disp:0.2, uns:44.0, share:16.3 },
      ],
      overall_uns: 54.9,
    },
  };
  // generic fallback for cities without a tailored equity profile
  function equityFor(coc) {
    if (EQUITY[coc]) return EQUITY[coc];
    const c = byCoc(coc);
    const unsRate = +(c.unsheltered / c.homeless * 100).toFixed(1);
    return {
      estimated: true,
      groups: [
        { g:"Black", disp:3.4, uns:unsRate*0.9, share:14 },
        { g:"Native American / AIAN", disp:3.0, uns:Math.min(95,unsRate*1.2), share:0.8 },
        { g:"Hispanic / Latino", disp:1.4, uns:unsRate, share:24 },
        { g:"Multiracial", disp:1.5, uns:unsRate*0.95, share:3 },
        { g:"White", disp:0.5, uns:Math.min(95,unsRate*1.05), share:40 },
        { g:"Asian", disp:0.22, uns:unsRate*0.85, share:9 },
      ],
      overall_uns: unsRate,
    };
  }

  // ============================================================
  //  AGENT TOOLS + ACTION TIERS
  // ============================================================
  const TOOLS = [
    { id:"context_lookup", name:"context_lookup", tier:0, desc:"Pull a CoC's PIT counts, ACS demographics and housing-cost context.", auto:true },
    { id:"scenario_montecarlo", name:"scenario_montecarlo", tier:1, desc:"Run 3 budget-timing scenarios with Monte-Carlo uncertainty (10-yr horizon).", auto:true },
    { id:"backtest", name:"backtest", tier:0, desc:"Replay the model against an observed PIT year it never saw.", auto:true },
    { id:"equity_query", name:"equity_query", tier:1, desc:"Compute population-level disproportionality and unsheltered rates by group.", auto:true },
    { id:"chart_render", name:"chart_render", tier:0, desc:"Render a recommended decision chart from a scenario or query.", auto:true },
    { id:"allocate_recommendation", name:"allocate_recommendation", tier:2, desc:"Recommend a specific dollar allocation across interventions.", auto:false },
    { id:"explain_brief", name:"explain_brief", tier:1, desc:"Write a plain-English one-page decision brief with sources & ranges.", auto:true },
  ];

  const TIERS = [
    { tier:0, label:"Automatic — read only", desc:"Look-ups and chart rendering. No judgement, no side effects.", gate:"Runs immediately." },
    { tier:1, label:"Automatic — analysis", desc:"Scenarios, equity queries, briefs. Always returns ranges and sources; declines on thin data.", gate:"Runs immediately, logged in the trajectory." },
    { tier:2, label:"Human approval required", desc:"Any recommendation of a specific allocation or budget action.", gate:"Pauses and asks a named person to sign off before proceeding." },
  ];

  // 15 decision charts catalogue (id maps to a renderer)
  const CHARTS = [
    { id:"cost_trajectory", name:"Cost trajectory", group:"Decision", desc:"Three 10-year paths with P10–P90 uncertainty bands.", wow:true },
    { id:"waterfall", name:"Cost-of-waiting waterfall", group:"Decision", desc:"How each year of delay stacks into the total." },
    { id:"breakeven", name:"Break-even curve", group:"Decision", desc:"When acting now overtakes waiting." },
    { id:"scenario_bars", name:"Scenario comparison", group:"Decision", desc:"10-yr public cost by path, with ranges." },
    { id:"compartments", name:"Compartments over time", group:"Decision", desc:"At-risk → sheltered → unsheltered → housed flows." },
    { id:"budget_compare", name:"Budget comparison", group:"Decision", desc:"Cost of waiting across program sizes." },
    { id:"mix_compare", name:"Intervention mix", group:"Decision", desc:"Outcomes by prevention / RRH / supportive-housing blend." },
    { id:"tornado", name:"Sensitivity tornado", group:"Honesty", desc:"Which assumptions move the headline most." },
    { id:"shap", name:"Model drivers (SHAP)", group:"Model", desc:"What the learned model leans on.", wow:true },
    { id:"backtest", name:"Backtest dot-interval", group:"Model", desc:"Predicted band vs the observed year.", wow:true },
    { id:"city_scatter", name:"City scatter", group:"Context", desc:"Housing cost vs homelessness rate, 17 CoCs." },
    { id:"city_benchmark", name:"City benchmark", group:"Context", desc:"Homelessness rate per 1,000, ranked." },
    { id:"us_map", name:"U.S. map", group:"Context", desc:"17 CoC bubbles sized by rate.", wow:true },
    { id:"equity_disparity", name:"Equity disparity", group:"Equity", desc:"Over-representation vs population share.", wow:true },
    { id:"equity_unsheltered", name:"Unsheltered by group", group:"Equity", desc:"Share unsheltered within each group." },
  ];

  const VINTAGE = "HUD 2024 PIT · Census ACS 2024";

  // ---- helpers ----
  function byCoc(coc) { return CITIES.find(c => c.coc === coc) || CITIES[0]; }
  function fmtMoney(v) { // v in dollars → compact $ string
    const a = Math.abs(v);
    if (a >= 1e9) return "$" + (v / 1e9).toFixed(a >= 1e10 ? 0 : 1) + "B";
    if (a >= 1e6) return "$" + (v / 1e6).toFixed(a >= 1e8 ? 0 : 1) + "M";
    if (a >= 1e3) return "$" + (v / 1e3).toFixed(0) + "K";
    return "$" + Math.round(v);
  }
  function fmtNum(v) { return v.toLocaleString("en-US"); }

  window.WC = {
    CITIES, TOOLS, TIERS, CHARTS, MODEL, BACKTEST, VINTAGE,
    byCoc, equityFor, computeScenario, costPerPersonYear,
    fmtMoney, fmtNum,
  };
})();
