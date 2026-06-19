// Typed fetch wrappers for every WaitCost backend route.
// Base resolution:
//   • dev (vite)      → "/api"  (proxied to :8000 by vite.config.ts)
//   • prod build      → ""      (same-origin: FastAPI serves both API and the app)
//   • override        → VITE_API_BASE  (e.g. a separately-hosted API URL)
import type {
  AskResult, Backtest, ChartCatalogItem, ChartSpec, Coc, Context, EffectBand,
  Equity, ModelPayload, Params, ScenarioPayload, CocPoint, ToolsPayload, CityBrief,
  ProvenanceMap,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "/api" : "");

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { signal });
  if (!res.ok) throw new ApiError(res.status, `${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new ApiError(res.status, `${path} → ${res.status}`);
  return res.json();
}

const qs = (o: Record<string, string | number | undefined>) =>
  Object.entries(o)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join("&");

export const api = {
  health: () => get<{ status: string }>("/health"),
  params: () => get<Params>("/params"),
  provenance: () => get<ProvenanceMap>("/provenance"),
  cocs: () => get<Coc[]>("/cocs"),
  tools: () => get<ToolsPayload>("/tools"),
  context: (coc: string, s?: AbortSignal) => get<Context>(`/context?coc=${coc}`, s),
  equity: (coc: string, s?: AbortSignal) => get<Equity>(`/equity?coc=${coc}`, s),
  cityBrief: (coc: string, s?: AbortSignal) => get<CityBrief>(`/city-brief?coc=${coc}`, s),
  charts: () => get<ChartCatalogItem[]>("/charts"),
  chart: (name: string, coc: string, budget_musd: number, delay_years: number,
          s?: AbortSignal, budgets?: string) =>
    get<ChartSpec>(`/chart?${qs({ name, coc, budget_musd, delay_years, budgets })}`, s),
  model: () => get<ModelPayload>("/model"),
  backtest: () => get<Backtest>("/backtest"),
  cocPoints: () => get<CocPoint[]>("/coc-points"),
  scenario: (
    body: { budget_musd: number; delay_years: number; n_mc?: number; mix?: Record<string, number> | null; coc?: string },
    s?: AbortSignal,
  ) => post<ScenarioPayload>("/scenario", body, s),
  effectBand: (budget_musd: number, delay_years: number, s?: AbortSignal) =>
    get<EffectBand>(`/effect-band?${qs({ budget_musd, delay_years })}`, s),
  ask: (body: { question: string; approve_allocation?: boolean; coc?: string }, s?: AbortSignal) =>
    post<AskResult>("/ask", body, s),
};

export { ApiError };
