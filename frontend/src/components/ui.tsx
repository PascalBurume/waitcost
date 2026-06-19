import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Icon } from "../lib/icons";
import { useApp } from "../state";

/* ---------------- provenance popover (Feature ①) ----------------
   Wraps any on-screen number; a tiny "ⓘ" reveals where it came from + its
   vintage + a "range, not a point" note, pulled from GET /provenance.
   Click- AND keyboard-focusable, with aria-describedby on the trigger. */
export function Provenance({ metric, children, label, entry: override, className }:
  { metric?: string; children: ReactNode; label?: string;
    entry?: { label?: string; source: string; publisher?: string; vintage?: string; note?: string };
    className?: string }) {
  const { provenance } = useApp();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const popId = useId();
  // Explicit `entry` (e.g. a chart's own source string) wins; otherwise look up the family.
  const entry = override ?? (metric ? provenance?.[metric] : undefined);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  // No provenance loaded (offline / not yet fetched): render the number plainly.
  if (!entry) return <>{children}</>;

  const name = label ?? entry.label ?? "Source";
  return (
    <span className={`prov${className ? ` ${className}` : ""}`} ref={wrapRef}>
      {children}
      <button
        type="button"
        className="prov-trigger"
        aria-label={`Source for ${name}`}
        aria-expanded={open}
        aria-describedby={open ? popId : undefined}
        onMouseDown={(e) => e.preventDefault()}   /* don't steal focus on mouse — let click toggle cleanly */
        onClick={() => setOpen((o) => !o)}
        onFocus={() => setOpen(true)}
        onBlur={(e) => { if (!wrapRef.current?.contains(e.relatedTarget as Node)) setOpen(false); }}
        onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
      >
        <Icon.Info size={12} />
      </button>
      {open && (
        <span id={popId} role="tooltip" className="prov-pop">
          <span className="prov-pop-label">{name}</span>
          <span className="prov-pop-row"><b>Source</b> {entry.source}</span>
          {entry.publisher && <span className="prov-pop-row"><b>Publisher</b> {entry.publisher}</span>}
          {entry.vintage && <span className="prov-pop-row"><b>Vintage</b> {entry.vintage}</span>}
          {entry.note && <span className="prov-pop-note">{entry.note}</span>}
        </span>
      )}
    </span>
  );
}

/* ---------------- skeleton ---------------- */
export function Skel({ h = 16, w = "100%", style }: { h?: number | string; w?: number | string; style?: React.CSSProperties }) {
  return <div className="skel" style={{ height: h, width: w, ...style }} aria-hidden />;
}

export function ChartSkel({ h = 360 }: { h?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading chart">
      <Skel h={h} style={{ borderRadius: 10 }} />
    </div>
  );
}

/* ---------------- error / empty ---------------- */
export function ErrorState({ error, onRetry, label = "Couldn't load this view" }:
  { error: Error; onRetry?: () => void; label?: string }) {
  const conn = /Failed to fetch|NetworkError|load failed/i.test(error.message);
  return (
    <div className="card" style={{ padding: 28, textAlign: "center", maxWidth: 520, margin: "20px auto" }} role="alert">
      <div className="declined-ico" style={{ marginBottom: 14 }}><Icon.Info size={24} /></div>
      <div style={{ fontWeight: 600, fontSize: "var(--fs-h3)" }}>{label}</div>
      <p className="muted" style={{ marginTop: 8, lineHeight: 1.55 }}>
        {conn
          ? "The WaitCost engine isn't responding. Start it with “uvicorn api.main:app --reload --port 8000” and retry."
          : error.message}
      </p>
      {onRetry && <button className="btn btn-ghost btn-sm" style={{ marginTop: 16 }} onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="card" style={{ padding: 26, textAlign: "center", color: "var(--ink-3)" }}>
      {children}
    </div>
  );
}

/* ---------------- pills / badges ---------------- */
export function Pill({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return <span className="pill" style={style}>{children}</span>;
}

const TIER_LABEL = ["Tier 0 · read", "Tier 1 · analysis", "Tier 2 · approval"];
export function TierBadge({ tier, compact = false }: { tier: 0 | 1 | 2; compact?: boolean }) {
  return (
    <span className={`tier tier-${tier}`} title={TIER_LABEL[tier]} style={{ whiteSpace: "nowrap" }}>
      {tier === 2 && <Icon.Lock size={11} />}
      {compact ? `T${tier}` : TIER_LABEL[tier]}
    </span>
  );
}

/* ---------------- stat tile ---------------- */
export function StatTile({ label, value, sub, big, accent, prov }:
  { label: string; value: ReactNode; sub?: ReactNode; big?: boolean; accent?: string; prov?: string }) {
  const val = <span className={`stat-tile-val tnum${big ? " big" : ""}`} style={accent ? { color: accent } : undefined}>{value}</span>;
  return (
    <div className="stat-tile">
      <div className="stat-tile-label">{label}</div>
      <div className="stat-tile-valrow">{prov ? <Provenance metric={prov} label={label}>{val}</Provenance> : val}</div>
      {sub && <div className="stat-tile-sub">{sub}</div>}
    </div>
  );
}

/* ---------------- modal (focus-trap + Esc) ---------------- */
export function Modal({ open, onClose, labelledBy, children }:
  { open: boolean; onClose: () => void; labelledBy: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const prevFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    prevFocus.current = document.activeElement as HTMLElement;
    const node = ref.current;
    const focusables = () =>
      node ? Array.from(node.querySelectorAll<HTMLElement>(
        'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'))
        .filter((el) => !el.hasAttribute("disabled")) : [];
    focusables()[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key === "Tab") {
        const f = focusables();
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prevFocus.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={labelledBy} ref={ref}>
        {children}
      </div>
    </div>
  );
}
