// Real U.S. geography (§6.5): d3-geo geoAlbersUsa + us-atlas TopoJSON, so every
// bubble sits at its true lat/lon — not the stylized mock outline.
import { useMemo } from "react";
import { geoAlbersUsa, geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";
import statesTopo from "us-atlas/states-10m.json";
import type { CocPoint } from "../api/types";
import { useTip } from "./primitives";
import { fmtNum } from "../lib/format";

const W = 720, H = 440;
const proj = geoAlbersUsa().scale(900).translate([W / 2, H / 2]);
const pathGen = geoPath(proj);

// Precompute once: states fill + the mesh of internal borders.
const topo = statesTopo as any;
const statesFeatures = (feature(topo, topo.objects.states) as any).features;
const borderMesh = mesh(topo, topo.objects.states, (a: any, b: any) => a !== b);
const nationMesh = mesh(topo, topo.objects.states, (a: any, b: any) => a === b);

export function USMap({ points, selected, onSelect }: {
  points: CocPoint[];
  selected: string;
  onSelect?: (coc: string) => void;
}) {
  const { show, hide, node } = useTip();
  const maxRate = useMemo(() => Math.max(...points.map((p) => p.rate_per_1k), 1), [points]);
  const r = (rate: number) => 5 + 20 * Math.sqrt(Math.max(rate, 0) / maxRate);

  const placed = points
    .map((p) => ({ p, xy: proj([p.lon, p.lat]) as [number, number] | null }))
    .filter((d): d is { p: CocPoint; xy: [number, number] } => d.xy != null)
    // draw larger bubbles first so small ones stay clickable on top
    .sort((a, b) => b.p.rate_per_1k - a.p.rate_per_1k);

  return (
    <div className="chart-frame">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
        aria-label="U.S. map of the 17 Continuum-of-Care cities, each bubble sized by homelessness rate per 1,000 residents.">
        <g>
          {statesFeatures.map((f: any) => (
            <path key={f.id} d={pathGen(f) || ""} fill="var(--canvas-2)" stroke="none" />
          ))}
          <path d={pathGen(borderMesh) || ""} fill="none" stroke="var(--hairline-2)" strokeWidth="0.6" />
          <path d={pathGen(nationMesh) || ""} fill="none" stroke="var(--axis)" strokeWidth="1" />
        </g>
        {placed.map(({ p, xy }) => {
          const isSel = p.coc === selected;
          return (
            <g key={p.coc} style={{ cursor: onSelect ? "pointer" : "default" }}
              role={onSelect ? "button" : undefined}
              tabIndex={onSelect ? 0 : undefined}
              aria-label={onSelect ? `${p.name}, rate ${p.rate_per_1k} per 1,000${isSel ? ", selected" : ""}` : undefined}
              onClick={() => onSelect?.(p.coc)}
              onKeyDown={(e) => { if (onSelect && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onSelect(p.coc); } }}
              onMouseMove={(e) => show(e, (
                <div>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>{p.name}</div>
                  <div className="tip-row"><span className="tip-k">Rate / 1,000</span><span>{p.rate_per_1k}</span></div>
                  <div className="tip-row"><span className="tip-k">PIT count</span><span>{fmtNum(p.pit_total)}</span></div>
                </div>
              ))}
              onMouseLeave={hide}>
              <circle cx={xy[0]} cy={xy[1]} r={r(p.rate_per_1k)}
                fill={isSel ? "var(--viz-act)" : "var(--viz-wait)"}
                fillOpacity={isSel ? 0.5 : 0.32}
                stroke={isSel ? "var(--viz-act)" : "var(--viz-wait)"}
                strokeWidth={isSel ? 2.5 : 1.4} />
              {isSel && <circle cx={xy[0]} cy={xy[1]} r={3} fill="var(--viz-act)" />}
            </g>
          );
        })}
      </svg>
      <div className="legend" style={{ marginTop: 10 }}>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--viz-wait)", opacity: 0.4 }} />City (bubble area ∝ rate / 1,000)</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--viz-act)", opacity: 0.5 }} />Selected city</span>
      </div>
      {node}
    </div>
  );
}
