/* ============================================================
   WaitCost — app shell, navigation, global state, tweaks
   ============================================================ */
const { useState: useS, useEffect: useE, useMemo: useM, useRef: useR } = React;

const NAV = [
  { id: "ask", label: "Ask", icon: "spark" },
  { id: "explore", label: "Explore", icon: "sliders" },
  { id: "visualize", label: "Visualize", icon: "chart" },
  { id: "model", label: "Where's the AI", icon: "cpu" },
  { id: "equity", label: "Equity", icon: "scale" },
  { id: "governance", label: "Governance", icon: "shield" },
  { id: "map", label: "Map", icon: "map" },
];

function NavIcon({ name }) {
  const p = { width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
  const m = {
    spark: <><path d="M12 3v3M12 18v3M5 12H2M22 12h-3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/></>,
    sliders: <><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></>,
    chart: <><line x1="5" y1="20" x2="5" y2="12"/><line x1="12" y1="20" x2="12" y2="6"/><line x1="19" y1="20" x2="19" y2="14"/></>,
    cpu: <><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/></>,
    scale: <><path d="M12 3v18M5 7h14M7 7l-3 7h6zM17 7l-3 7h6z"/></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>,
    map: <path d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3Z"/>,
  };
  return <svg {...p} className="tab-ico">{m[name]}</svg>;
}

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="var(--accent)" />
      {/* an hourglass-of-cost: rising bars under a clock tick */}
      <path d="M16 7v9l5 3" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      <circle cx="16" cy="16" r="9.5" stroke="#fff" strokeWidth="2" opacity=".55" fill="none"/>
    </svg>
  );
}

function CitySelect({ city, onSelect }) {
  const [open, setOpen] = useS(false);
  const ref = useR(null);
  useE(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  return (
    <div className="city-select" ref={ref}>
      <button className="city-select-btn" aria-expanded={open} aria-haspopup="listbox" onClick={() => setOpen(!open)}>
        <span className="label">City</span>
        <span className="name">{city.name}</span>
        <svg className="chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      {open && (
        <div className="city-menu" role="listbox">
          {WC.CITIES.map(c => (
            <button key={c.coc} role="option" aria-selected={c.coc === city.coc} className="city-opt"
              onClick={() => { onSelect(c.coc); setOpen(false); }}>
              <span className="col" style={{ alignItems: "flex-start", gap: 1 }}>
                <span className="nm">{c.name}{c.real && <span className="pill" style={{ marginLeft: 7, padding: "1px 6px", fontSize: 10 }}>measured</span>}</span>
                <span className="meta">CoC {c.coc} · {c.st}</span>
              </span>
              <span className="meta tnum">{c.rate}/1k</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const ACCENTS = ["#1A56DB", "#1F6F5C", "#5B49C9", "#1C5D8C"];
const PALETTES = [
  { name: "Indigo / Clay", act: "var(--accent)", wait: "#C2740C", neutral: "#8C877B" },
  { name: "Blue / Orange", act: "var(--accent)", wait: "#D26A1B", neutral: "#8A8578" },
  { name: "Teal / Amber", act: "var(--accent)", wait: "#B08400", neutral: "#8C887C" },
];

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "dark": false,
  "accent": "#1A56DB",
  "palette": 0,
  "uiFont": "Public Sans",
  "memoFont": "Source Serif 4",
  "showBands": true,
  "density": "regular"
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [tab, setTab] = useS("ask");
  const [coc, setCoc] = useS("CA-600");
  const [explore, setExplore] = useS({ budget: 15, delay: 3, mix: { prev: 34, rrh: 33, psh: 33 } });
  const [vizSel, setVizSel] = useS("cost_trajectory");

  const city = useM(() => WC.byCoc(coc), [coc]);
  const baseScn = useM(() => WC.computeScenario({ city, budget: 15, delay: 3, mix: { prev: 0.34, rrh: 0.33, psh: 0.33 } }), [city]);

  // apply theme + tokens
  useE(() => {
    const r = document.documentElement;
    r.setAttribute("data-theme", t.dark ? "dark" : "light");
    const acc = t.dark ? mixHex(t.accent, "#ffffff", 0.32) : t.accent;
    r.style.setProperty("--accent", acc);
    // derive accent-ink / soft from accent
    r.style.setProperty("--accent-ink", t.dark ? mixHex(t.accent, "#ffffff", 0.5) : mixHex(t.accent, "#000000", 0.28));
    r.style.setProperty("--accent-soft", t.dark ? mixHex(t.accent, "#15140f", 0.78) : mixHex(t.accent, "#ffffff", 0.88));
    const pal = PALETTES[t.palette] || PALETTES[0];
    r.style.setProperty("--viz-act", "var(--accent)");
    r.style.setProperty("--viz-wait", pal.wait);
    r.style.setProperty("--viz-neutral", pal.neutral);
    r.style.setProperty("--ui", `"${t.uiFont}", system-ui, sans-serif`);
    r.style.setProperty("--serif", `"${t.memoFont}", Georgia, serif`);
    r.style.setProperty("--fs-base", t.density === "compact" ? "14px" : t.density === "comfy" ? "16px" : "15px");
  }, [t]);

  function goChart(id) { setVizSel(id); setTab("visualize"); }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-row">
          <div className="brand"><BrandMark /> WaitCost <span className="brand-sub">· cost of doing nothing</span></div>
          <span className="vintage-chip"><span className="dot"></span>{WC.VINTAGE}</span>
          <span className="spacer"></span>
          <CitySelect city={city} onSelect={setCoc} />
        </div>
        <div className="disclaimer">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          Informs a budget-timing tradeoff. Does not decide allocations or forecast individuals. All figures are ranges.
        </div>
        <nav className="nav" aria-label="Primary">
          {NAV.map(n => (
            <button key={n.id} className="nav-tab" aria-current={tab === n.id ? "page" : undefined} onClick={() => setTab(n.id)}>
              <NavIcon name={n.icon} />{n.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="main">
        {tab === "ask" && <AskScreen key={coc} city={city} scn={baseScn} onSeeChart={goChart} showBands={t.showBands} />}
        {tab === "explore" && <ExploreScreen city={city} controls={explore} setControls={setExplore} showBands={t.showBands} />}
        {tab === "visualize" && <VisualizeScreen city={city} scn={baseScn} selected={vizSel} setSelected={setVizSel} onSelectCity={setCoc} showBands={t.showBands} />}
        {tab === "model" && <ModelScreen city={city} onSelectCity={setCoc} />}
        {tab === "equity" && <EquityScreen city={city} />}
        {tab === "governance" && <GovernanceScreen city={city} />}
        {tab === "map" && <MapScreen city={city} scn={baseScn} onSelectCity={setCoc} />}
      </main>

      <TweaksPanel>
        <TweakSection label="Appearance" />
        <TweakToggle label="Dark mode" value={t.dark} onChange={v => setTweak("dark", v)} />
        <TweakColor label="Accent" value={t.accent} options={ACCENTS} onChange={v => setTweak("accent", v)} />
        <TweakSelect label="Chart palette" value={String(t.palette)} options={PALETTES.map((p, i) => ({ value: String(i), label: p.name }))} onChange={v => setTweak("palette", +v)} />
        <TweakRadio label="Density" value={t.density} options={["compact", "regular", "comfy"]} onChange={v => setTweak("density", v)} />
        <TweakSection label="Typography" />
        <TweakSelect label="UI typeface" value={t.uiFont} options={["Public Sans", "IBM Plex Sans"]} onChange={v => setTweak("uiFont", v)} />
        <TweakSelect label="Memo serif" value={t.memoFont} options={["Source Serif 4", "Newsreader"]} onChange={v => setTweak("memoFont", v)} />
        <TweakSection label="Data display" />
        <TweakToggle label="Show uncertainty bands" value={t.showBands} onChange={v => setTweak("showBands", v)} />
      </TweaksPanel>
    </div>
  );
}

/* hex blend helper for derived accent tones */
function mixHex(a, b, w) {
  const pa = hx(a), pb = hx(b);
  const r = Math.round(pa[0]*(1-w)+pb[0]*w), g = Math.round(pa[1]*(1-w)+pb[1]*w), bl = Math.round(pa[2]*(1-w)+pb[2]*w);
  return "#" + [r, g, bl].map(v => v.toString(16).padStart(2, "0")).join("");
}
function hx(h) { h = h.replace("#",""); if (h.length===3) h=h.split("").map(c=>c+c).join(""); return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)]; }

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
