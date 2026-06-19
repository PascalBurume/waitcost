import { useEffect, useRef, useState } from "react";
import { useApp } from "../state";
import { Icon, type IconName } from "../lib/icons";
import { fmtNum } from "../lib/format";

/* ---------------- brand mark ---------------- */
function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 26 26" aria-hidden>
      <circle cx="13" cy="13" r="12" fill="none" stroke="var(--accent)" strokeWidth="2" />
      <path d="M13 7v6l4 3" fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ---------------- city selector ---------------- */
function CitySelector() {
  const { coc, setCoc, cocs } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = cocs.find((c) => c.coc === coc);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <div className="city-select" ref={ref}>
      <button className="city-select-btn" aria-expanded={open} aria-haspopup="listbox"
        onClick={() => setOpen((o) => !o)}>
        <span className="label">City</span>
        <span className="name">{current?.name ?? coc}</span>
        <Icon.Chevron size={15} className="chev" />
      </button>
      {open && (
        <div className="city-menu" role="listbox" aria-label="Select a Continuum of Care">
          {cocs.map((c) => (
            <button key={c.coc} className="city-opt" role="option" aria-selected={c.coc === coc}
              onClick={() => { setCoc(c.coc); setOpen(false); }}>
              <span><span className="nm">{c.name}</span> <span className="meta">{c.coc}</span></span>
              <span className="meta tnum">{fmtNum(c.pit_total)} PIT</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------- theme toggle (the only shipped tweak — §6.4) ---------------- */
function ThemeToggle() {
  const { theme, toggleTheme } = useApp();
  const dark = theme === "dark";
  return (
    <button className="btn btn-ghost btn-sm" onClick={toggleTheme}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={dark}
      style={{ minHeight: 36 }}>
      {dark ? <Icon.Sun size={16} /> : <Icon.Moon size={16} />}
    </button>
  );
}

/* ---------------- topbar ---------------- */
export function Topbar() {
  const { params } = useApp();
  return (
    <header className="topbar">
      <div className="topbar-row">
        <div className="brand">
          <BrandMark />
          <span>WaitCost</span>
          <span className="brand-sub">Cost of Doing Nothing</span>
        </div>
        <div className="spacer" />
        <span className="vintage-chip"><span className="dot" />{`HUD 2024 PIT · Census ACS 2024${(params?.acs_release ?? "ACS 2024 1-yr (API)").includes("API") ? " (API)" : ""}`}</span>
        <CitySelector />
        <ThemeToggle />
      </div>
    </header>
  );
}

export function DisclaimerBar() {
  return (
    <div className="disclaimer" role="note">
      <Icon.Info size={14} />
      <span style={{ whiteSpace: "normal" }}>
        Informs a budget-timing tradeoff. Does not decide allocations or forecast individuals. All figures are ranges.
      </span>
    </div>
  );
}

/* ---------------- nav ---------------- */
export const TABS: { id: string; label: string; icon: IconName }[] = [
  { id: "ask", label: "Ask", icon: "Ask" },
  { id: "explore", label: "Explore", icon: "Explore" },
  { id: "visualize", label: "Visualize", icon: "Visualize" },
  { id: "model", label: "Where's the AI", icon: "Brain" },
  { id: "equity", label: "Equity", icon: "Equity" },
  { id: "governance", label: "Governance", icon: "Shield" },
  { id: "map", label: "Map", icon: "Map" },
];

export function Nav({ active, onChange }: { active: string; onChange: (id: string) => void }) {
  return (
    <nav className="nav" aria-label="Primary">
      {TABS.map((t) => {
        const I = Icon[t.icon];
        return (
          <button key={t.id} className="nav-tab" aria-current={active === t.id ? "page" : undefined}
            onClick={() => onChange(t.id)}>
            <I size={16} className="tab-ico" />{t.label}
          </button>
        );
      })}
    </nav>
  );
}
