import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { ChartCatalogItem, ChartSpec } from "../api/types";
import { useApp, useCityName } from "../state";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../lib/icons";
import { ChartSkel, ErrorState } from "../components/ui";
import { ChartView } from "../charts/ChartView";

const GROUP_ORDER = ["cost_of_waiting", "savings_now", "break_even", "compare_budgets", "compare_mix", "outcome_at_horizon", "sensitivity", "model", "city_context", "equity"];
const GROUP_LABEL: Record<string, string> = {
  cost_of_waiting: "Decision", savings_now: "Decision", break_even: "Decision",
  compare_budgets: "Decision", compare_mix: "Decision", outcome_at_horizon: "Decision",
  sensitivity: "Honesty", model: "Model", city_context: "Context", equity: "Equity",
};
const WOW = new Set(["cost_trajectory", "shap_drivers", "backtest", "city_map", "equity_disparity"]);

export function VisualizeScreen() {
  const { coc } = useApp();
  const city = useCityName(coc);
  const catalog = useAsync(() => api.charts(), []);
  const [selected, setSelected] = useState("cost_trajectory");

  const spec = useAsync<ChartSpec>(
    (s) => api.chart(selected, coc, 15, 3, s),
    [selected, coc],
  );

  const grouped = useMemo(() => {
    const items = catalog.data ?? [];
    const byGroup = new Map<string, ChartCatalogItem[]>();
    for (const it of items) {
      const g = GROUP_LABEL[it.intent] ?? "More";
      if (!byGroup.has(g)) byGroup.set(g, []);
      byGroup.get(g)!.push(it);
    }
    const order = ["Decision", "Honesty", "Model", "Context", "Equity", "More"];
    return order.filter((g) => byGroup.has(g)).map((g) => [g, byGroup.get(g)!] as const);
  }, [catalog.data]);

  const current = (catalog.data ?? []).find((c) => c.name === selected);

  return (
    <div className="page page-wide">
      <div className="section-head">
        <span className="eyebrow">Visualize · {city}</span>
        <h1 className="page-title serif">Fifteen decision charts</h1>
        <p className="lede">Pick a chart; the engine renders it live for {city}. Each carries a caption and its data source.</p>
      </div>

      <div className="viz-layout">
        <div className="viz-picker">
          {catalog.loading && <ChartSkel h={300} />}
          {grouped.map(([group, items]) => (
            <div key={group}>
              <div className="viz-group-label">{group}</div>
              {items.map((it) => (
                <button key={it.name} className={`viz-pick${it.name === selected ? " active" : ""}`}
                  onClick={() => setSelected(it.name)} aria-pressed={it.name === selected}>
                  <span className="viz-pick-spark"><Icon.Visualize size={16} /></span>
                  <span className="viz-pick-text">
                    <span className="viz-pick-name">{prettyName(it.name)}{WOW.has(it.name) && <span className="wow-dot" title="signature chart" />}</span>
                    <span className="viz-pick-desc">{it.when}</span>
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="card viz-stage">
          {spec.error ? <ErrorState error={spec.error} onRetry={spec.reload} label="Couldn't render this chart" /> : (
            <>
              <div className="viz-stage-head">
                <div>
                  <span className="chart-title">{spec.data?.title ?? prettyName(selected)}</span>
                  {current && <div className="muted" style={{ fontSize: "var(--fs-sm)", marginTop: 2 }}>{current.when}</div>}
                </div>
                <span className="pill">{current?.kind ?? spec.data?.kind}</span>
              </div>
              <div className="viz-stage-body" key={selected + coc}>
                {spec.loading || !spec.data ? <ChartSkel h={420} /> : <ChartView spec={spec.data} height={440} />}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function prettyName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/Shap/, "SHAP").replace(/Coc/, "CoC");
}
