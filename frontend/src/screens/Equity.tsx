import { api } from "../api/client";
import type { ChartSpec, Equity } from "../api/types";
import { useApp, useCityName } from "../state";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../lib/icons";
import { ChartSkel, ErrorState, Provenance } from "../components/ui";
import { ChartView } from "../charts/ChartView";

export function EquityScreen() {
  const { coc } = useApp();
  const city = useCityName(coc);
  const eq = useAsync<Equity>((s) => api.equity(coc, s), [coc]);
  const disparity = useAsync<ChartSpec>((s) => api.chart("equity_disparity", coc, 15, 3, s), [coc]);
  const unsheltered = useAsync<ChartSpec>((s) => api.chart("equity_unsheltered", coc, 15, 3, s), [coc]);

  if (eq.error) return <div className="page"><ErrorState error={eq.error} onRetry={eq.reload} /></div>;
  const d = eq.data;
  const lead = d?.most_overrepresented;

  return (
    <div className="page page-wide">
      <div className="section-head">
        <span className="eyebrow">Equity · {city}</span>
        <h1 className="page-title serif">Who bears this</h1>
      </div>

      <div className="card equity-callout">
        <span className="equity-callout-ico"><Icon.Scale size={20} /></span>
        <div>
          <div className="equity-callout-h">Population-level only — never individuals</div>
          <div className="equity-callout-b">
            These figures compare groups to their share of the population. WaitCost does not, and will not, profile or
            score any person. Disproportionality is a measure of who the system fails, not a targeting tool.
          </div>
        </div>
      </div>

      <div className="card equity-lead">
        <Provenance metric="equity" label="Disproportionality">
          <span className="equity-lead-num tnum">{lead ? `${lead.factor.toFixed(1)}×` : "—"}</span>
        </Provenance>
        <p>
          {lead ? <><b>{lead.group}</b> residents are <b>{lead.factor.toFixed(1)}×</b> over-represented among {city}'s homeless population
            relative to their share of residents — the largest disparity in the city.</> : "Loading the city's disparities…"}
        </p>
      </div>

      <div className="equity-grid">
        <div className="card chart-card">
          <span className="chart-title">Disproportionality vs population share</span>
          <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "4px 0 8px" }}>Bars past the 1.0× line are over-represented (clay).</p>
          {disparity.loading || !disparity.data ? <ChartSkel h={420} /> : <ChartView spec={disparity.data} height={420} />}
        </div>
        <div className="card chart-card">
          <span className="chart-title">Unsheltered rate within each group</span>
          <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "4px 0 8px" }}>
            Share of each group's homeless who are unsheltered{d ? ` · citywide ${citywide(d)}%` : ""}.
          </p>
          {unsheltered.loading || !unsheltered.data ? <ChartSkel h={420} /> : <ChartView spec={unsheltered.data} height={420} />}
        </div>
      </div>

      {d && (
        <p className="muted" style={{ fontSize: "var(--fs-sm)", marginTop: 16 }}>
          <Provenance metric="equity" label="Equity data"><span aria-hidden>◆</span> {d.source}</Provenance>
        </p>
      )}
    </div>
  );
}

function citywide(d: Equity): string {
  // Weighted unsheltered rate across groups, by homeless share — population-level.
  const w = d.groups.reduce((a, g) => a + g.unsheltered_rate_pct * g.homeless_share_pct, 0);
  const tot = d.groups.reduce((a, g) => a + g.homeless_share_pct, 0) || 1;
  return (w / tot).toFixed(1);
}
