// Hand-built SVG chart primitives — theme-aware via CSS vars, colorblind-safe.
// Mirrors the design's charts-core.jsx idiom (Axes frame, lin scale, area paths).
import { useCallback, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export const lin = (d0: number, d1: number, r0: number, r1: number) => (v: number) =>
  r0 + (r1 - r0) * ((v - d0) / (d1 - d0 || 1));

/** A "nice" axis bound rounded up to 1/2/5 × 10^n. */
export function niceMax(v: number): number {
  if (v <= 0) return 1;
  const e = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / e;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * e;
}

export function pathFrom(pts: [number, number][]): string {
  return pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
}
export function areaFrom(top: [number, number][], bot: [number, number][]): string {
  const last = bot[bot.length - 1];
  return (
    pathFrom(top) + " L" + last[0].toFixed(1) + " " + last[1].toFixed(1) + " " +
    bot.slice().reverse().map((p) => "L" + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ") + " Z"
  );
}

/** Map a backend series to the colorblind-safe design trio by ROLE (never the
 *  raw hex the API returns — the spec ships fire-engine red, which is banned). */
export function vizColor(name: string, index = 0): string {
  const n = name.toLowerCase();
  if (/status quo|do nothing|nothing|neutral|at[- ]?risk|chronic/.test(n)) return "var(--viz-neutral)";
  // \bsheltered$ matches "sheltered" but NOT "unsheltered" (no word boundary before the 's').
  if (/act now|model|\bsheltered$|prediction|predicted|newly housed|housed/.test(n)) return "var(--viz-act)";
  if (/delay|wait|extra|unsheltered|disproportion|impact|rate|cost/.test(n)) return "var(--viz-wait)";
  if (/observed/.test(n)) return "var(--ink)";
  return ["var(--viz-act)", "var(--viz-wait)", "var(--viz-neutral)", "var(--viz-wait-2)"][index % 4];
}

/* ---------------- shared tooltip ---------------- */
export function useTip() {
  const [tip, setTip] = useState<{ x: number; y: number; content: ReactNode } | null>(null);
  const show = useCallback((e: React.MouseEvent, content: ReactNode) => {
    setTip({ x: e.clientX, y: e.clientY, content });
  }, []);
  const hide = useCallback(() => setTip(null), []);
  // Portal to <body> so the position:fixed tooltip is anchored to the viewport, not
  // to a transformed ancestor (e.g. the Ask answer's `.rise` animation), which would
  // otherwise become the containing block and push the tooltip off-screen.
  const node = tip
    ? createPortal(
        <div className="viz-tip" role="status"
          style={{ left: Math.min(tip.x + 14, window.innerWidth - 250), top: tip.y + 14 }}>
          {tip.content}
        </div>,
        document.body,
      )
    : null;
  return { show, hide, node };
}

export interface Pad { l: number; r: number; t: number; b: number; }

export function Axes({ x, y, w, h, pad, yTicks, xTicks, yFmt, xFmt, yLabel, xLabel }: {
  x: (v: number) => number; y: (v: number) => number; w: number; h: number; pad: Pad;
  yTicks: number[]; xTicks: number[]; yFmt: (t: number) => string; xFmt: (t: number) => string;
  yLabel?: string; xLabel?: string;
}) {
  return (
    <g>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
          <text x={pad.l - 9} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize="12"
            fill="var(--ink-3)" style={{ fontVariantNumeric: "tabular-nums" }}>{yFmt(t)}</text>
        </g>
      ))}
      {xTicks.map((t, i) => (
        <text key={i} x={x(t)} y={h - pad.b + 18} textAnchor="middle" fontSize="12"
          fill="var(--ink-3)" style={{ fontVariantNumeric: "tabular-nums" }}>{xFmt(t)}</text>
      ))}
      <line x1={pad.l} x2={w - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--axis)" strokeWidth="1.25" />
      {xLabel && <text x={(pad.l + w - pad.r) / 2} y={h - 4} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)" fontWeight="600">{xLabel}</text>}
      {yLabel && <text transform={`translate(14 ${(pad.t + h - pad.b) / 2}) rotate(-90)`} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)" fontWeight="600">{yLabel}</text>}
    </g>
  );
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean; swatch?: boolean }[] }) {
  return (
    <div className="legend" style={{ marginTop: 12 }}>
      {items.map((it, i) => (
        <span key={i} className="legend-item">
          {it.swatch
            ? <span className="legend-swatch" style={{ background: it.color }} />
            : <span className="legend-line" style={{ borderTopColor: it.color, borderTopStyle: it.dashed ? "dashed" : "solid" }} />}
          {it.label}
        </span>
      ))}
    </div>
  );
}
