import { api } from "../api/client";
import type { CityBrief, ChartSpec, CocPoint, Context } from "../api/types";
import { useApp, useCityName } from "../state";
import { useAsync } from "../lib/useAsync";
import { fmtNum, fmtPct, fmtUsd } from "../lib/format";
import { ChartSkel, ErrorState, StatTile } from "../components/ui";
import { USMap } from "../charts/USMap";
import { ChartView } from "../charts/ChartView";

export function MapScreen() {
  const { coc, setCoc } = useApp();
  const city = useCityName(coc);
  const points = useAsync<CocPoint[]>(() => api.cocPoints(), []);
  const ctx = useAsync<Context>((s) => api.context(coc, s), [coc]);
  const brief = useAsync<CityBrief>((s) => api.cityBrief(coc, s), [coc]);
  const benchmark = useAsync<ChartSpec>((s) => api.chart("city_benchmark", coc, 50, 3, s), [coc]);

  if (points.error) return <div className="page"><ErrorState error={points.error} onRetry={points.reload} /></div>;
  const ind = ctx.data?.indicators;

  return (
    <div className="page page-wide">
      <div className="section-head">
        <span className="eyebrow">Map</span>
        <h1 className="page-title serif">Seventeen cities, one engine</h1>
        <p className="lede">Each bubble is a real Continuum of Care at its true location, sized by homelessness per 1,000 residents. Click a city to re-skin every screen.</p>
      </div>

      <div className="map-layout">
        <div className="card map-stage">
          {points.loading || !points.data ? <ChartSkel h={440} /> :
            <USMap points={points.data} selected={coc} onSelect={setCoc} />}
        </div>

        <div className="card map-panel">
          <div className="map-panel-eyebrow">
            <span className="eyebrow">Selected city</span>
            <span className="pill">{coc}</span>
          </div>
          <div className="map-city serif">{city}</div>
          <div className="map-coc">{ctx.data?.sources?.split(";")[0] ?? "HUD 2024 PIT · Census ACS 2024 (API)"}</div>

          {ctx.error ? <ErrorState error={ctx.error} onRetry={ctx.reload} label="City context unavailable" /> : (
            <div className="map-stats">
              <StatTile label="HOMELESS (PIT)" value={ind ? fmtNum(ind.homeless_pit_total) : "—"} prov="homeless_counts" />
              <StatTile label="RATE / 1,000" value={ind ? ind.homeless_rate_per_1k.toFixed(1) : "—"} prov="homeless_counts" />
              <StatTile label="UNSHELTERED" value={ind ? fmtPct(ind.unsheltered_share_pct) : "—"} prov="homeless_counts" />
              <StatTile label="MEDIAN HOME VALUE" value={ind ? fmtUsd(ind.median_home_value_usd) : "—"} prov="economic_features" />
            </div>
          )}

          {ind && (
            <div className="map-cow">
              <div className="map-cow-label">HOME-VALUE-TO-INCOME RATIO</div>
              <div className="map-cow-num tnum">{ind.home_value_to_income_ratio.toFixed(1)}×</div>
              <p className="muted" style={{ fontSize: "var(--fs-sm)" }}>
                Housing cost is the model's top driver of homelessness — see “Where's the AI”.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* The City Brief gets its own full-width row below the map+snapshot, so it has
          reading width and doesn't make the side column run far past the map. */}
      <CityBriefPanel brief={brief} benchmark={benchmark} />
    </div>
  );
}

function CityBriefPanel({ brief, benchmark }: {
  brief: ReturnType<typeof useAsync<CityBrief>>;
  benchmark: ReturnType<typeof useAsync<ChartSpec>>;
}) {
  const b = brief.data;
  return (
    <div className="card city-brief-card">
      <div className="map-panel-eyebrow" style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span className="eyebrow">City Brief</span>
        <span className="pill" title="This panel is qualitative context from cited sources — not the calibrated cost simulator.">
          General context — not the calibrated model
        </span>
        {b && <span className="pill" style={{ opacity: 0.8 }}>{b.online ? "● live" : "○ offline"}</span>}
      </div>

      {brief.error ? (
        <ErrorState error={brief.error} onRetry={brief.reload} label="City brief unavailable" />
      ) : !b ? (
        <ChartSkel h={140} />
      ) : (
        <div className="city-brief-grid">
          <div className="city-brief-main">
            {b.lead_agency && <p style={{ margin: "0 0 4px" }}><strong>Lead agency:</strong> {b.lead_agency}</p>}
            {b.plan?.title && (
              <p style={{ margin: "0 0 8px" }}>
                <strong>Care plan:</strong>{" "}
                {b.plan.url ? <a href={b.plan.url} target="_blank" rel="noreferrer noopener">{b.plan.title}</a> : b.plan.title}
              </p>
            )}
            <p className="muted">{stripMd(b.situation)}</p>
            {b.plan?.summary && <p className="muted" style={{ marginTop: 8 }}><strong>Strategy.</strong> {stripMd(b.plan.summary)}</p>}
            {b.sources?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div className="map-cow-label">SOURCES</div>
                <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                  {b.sources.map((s) => (
                    <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.title}</a></li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Graphic: where this city sits among its peers (real HUD PIT rates). */}
          <div className="city-brief-chart">
            {benchmark.error ? null : !benchmark.data ? <ChartSkel h={300} /> : (
              <>
                <div className="chart-title" style={{ fontSize: "var(--fs-sm)", fontWeight: 700 }}>{benchmark.data.title}</div>
                {benchmark.data.subtitle && <div className="chart-cap" style={{ marginTop: 0, marginBottom: 6 }}>{benchmark.data.subtitle}</div>}
                <ChartView spec={benchmark.data} />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// The brief carries light markdown (**bold**) from the agent; the panel renders
// plain text, so strip the emphasis markers for a clean inline read.
function stripMd(s: string): string {
  return (s || "").replace(/\*\*/g, "");
}
