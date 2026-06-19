import { fmtMusd } from "../lib/format";
import { useTip } from "./primitives";
import { ChartSkel } from "../components/ui";

export interface Composition {
  total_musd: number;
  baseline_musd?: number;        // do-nothing 10-yr cost (for the "saves vs nothing" bar)
  saves_vs_nothing_musd?: number;
  groups: { key: string; label: string; cost_musd: number; pct: number }[];
}

const GROUP_COLOR: Record<string, string> = {
  chronic_unsheltered: "var(--viz-wait-2)",
  unsheltered: "#d4843f",
  sheltered: "var(--viz-wait)",
  at_risk: "var(--viz-neutral)",
  housed_stable: "#cfd6dc",
  exited_positive: "#cfd6dc",
};

function polar(cx: number, cy: number, r: number, a: number) {
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)] as const;
}
function arc(cx: number, cy: number, ro: number, ri: number, a0: number, a1: number) {
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const [x0, y0] = polar(cx, cy, ro, a0), [x1, y1] = polar(cx, cy, ro, a1);
  const [x2, y2] = polar(cx, cy, ri, a1), [x3, y3] = polar(cx, cy, ri, a0);
  return `M${x0} ${y0} A${ro} ${ro} 0 ${large} 1 ${x1} ${y1} L${x2} ${y2} A${ri} ${ri} 0 ${large} 0 ${x3} ${y3} Z`;
}

const fmtB = (m: number) => (m >= 1000 ? `$${(m / 1000).toFixed(1)}B` : fmtMusd(m));

/** Donut: where the program's 10-year public cost goes, by group, + a live bar
 *  showing how much it saves vs. doing nothing. */
export function CostDonut({ composition }: { composition?: Composition | null }) {
  const { show, hide, node } = useTip();
  if (!composition || !composition.groups.length) return <ChartSkel h={220} />;
  const cx = 110, cy = 110, ro = 92, ri = 58;
  let a = -Math.PI / 2;
  const segs = composition.groups.map((g) => {
    const a0 = a, a1 = a + (g.pct / 100) * Math.PI * 2;
    a = a1;
    return { g, d: arc(cx, cy, ro, ri, a0, Math.max(a1, a0 + 0.0001)) };
  });
  const total = composition.total_musd;
  const baseline = composition.baseline_musd ?? total;
  const saves = composition.saves_vs_nothing_musd ?? 0;
  const SAVED = "#1d9e75";
  return (
    <div style={{ display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
      <svg viewBox="0 0 220 220" width="220" height="220" role="img"
        aria-label="Where the 10-year public cost goes, by group">
        {segs.map((s) => (
          <path key={s.g.key} d={s.d} fill={GROUP_COLOR[s.g.key] ?? "var(--viz-neutral)"}
            stroke="var(--surface)" strokeWidth="1.5"
            onMouseMove={(e) => show(e, (
              <div><b>{s.g.label}</b><div className="tip-row">
                <span className="tip-k">10-yr cost</span><span>{fmtMusd(s.g.cost_musd)} · {s.g.pct.toFixed(0)}%</span>
              </div></div>))} onMouseLeave={hide} />
        ))}
        <text x={cx} y={cy - 5} textAnchor="middle" fontSize="25" fontWeight="800" fill="var(--ink)"
          style={{ fontVariantNumeric: "tabular-nums" }}>{fmtB(total)}</text>
        <text x={cx} y={cy + 16} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)">this program · 10 yrs</text>
      </svg>
      <div style={{ flex: 1, minWidth: 230 }}>
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {composition.groups.map((g) => (
            <li key={g.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "1px solid var(--hairline)" }}>
              <span style={{ width: 11, height: 11, borderRadius: 3, background: GROUP_COLOR[g.key] ?? "var(--viz-neutral)", flex: "0 0 auto" }} />
              <span style={{ flex: 1, fontSize: "var(--fs-sm)" }}>{g.label}</span>
              <span className="tnum" style={{ fontWeight: 700 }}>{g.pct.toFixed(0)}%</span>
              <span className="tnum" style={{ color: "var(--ink-2)", minWidth: 76, textAlign: "right" }}>{fmtMusd(g.cost_musd)}</span>
            </li>
          ))}
        </ul>
        <div style={{ marginTop: 10 }}>
          {/* The full bar is the do-nothing baseline; the green tail is what this
              program saves. Tune the budget/mix and watch the green grow. */}
          <div style={{ display: "flex", height: 10, borderRadius: 5, overflow: "hidden", background: "var(--viz-band)" }}>
            <div style={{ width: `${(total / baseline) * 100}%`, background: "var(--viz-wait-2)" }} title="program cost" />
            <div style={{ width: `${(saves / baseline) * 100}%`, background: SAVED }} title="saved vs. doing nothing" />
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 5 }}>
            This program costs <b>{fmtB(total)}</b> over 10 years —{" "}
            {saves > 0
              ? <span><b style={{ color: SAVED }}>saves {fmtMusd(saves)}</b> vs. doing nothing ({fmtB(baseline)}).</span>
              : <span>doing nothing also costs {fmtB(baseline)}. Fund a program to start saving.</span>}
          </div>
        </div>
      </div>
      {node}
    </div>
  );
}
