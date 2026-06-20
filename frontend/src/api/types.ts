// Types mirror the live FastAPI payloads (api/payloads.py). Payloads that carry
// many engine internals are kept loose on purpose — we only type what the UI reads.

export interface Params {
  coc: string;
  data_vintage: string;
  acs_release: string;     // ACS provenance/vintage from the panel, e.g. "ACS 2024 1-yr (API)"
  horizon_years: number;
  discount_annual: number;
  default_budget_musd: number;
}

export interface Coc {
  coc: string;
  name: string;
  pit_total: number;
}

// Feature ① — where each on-screen number comes from, keyed by metric family.
export interface ProvenanceEntry {
  label: string;
  source: string;
  publisher?: string;
  vintage: string;
  link?: string;
  note: string;
}
export type ProvenanceMap = Record<string, ProvenanceEntry>;

export interface Capability {
  name: string;
  tier: 0 | 1 | 2;
  params: string[];
  desc: string;
}
export interface ToolsPayload {
  agents: number;
  agent_names: string[];
  capabilities: Capability[];
  skills: number;
  charts: number;
  capability_names: string[];
  skill_names: string[];
  chart_names: string[];
}

export interface Context {
  coc: string;
  name: string;
  indicators: {
    population: number;
    homeless_pit_total: number;
    homeless_rate_per_1k: number;
    unsheltered_share_pct: number;
    chronic_share_pct: number;
    median_home_value_usd: number;
    median_household_income_usd: number;
    poverty_rate_pct: number;
    home_value_to_income_ratio: number;
  };
  live: boolean;
  sources: string;
}

// The third agent (CityBriefAgent): grounded, cited city context — NOT the cost model.
export interface CityBriefSource {
  title: string;
  url: string;
}
export interface CityBrief {
  coc: string;
  city: string;
  lead_agency: string | null;
  plan: { title: string | null; url: string | null; summary: string };
  situation: string;
  indicators: Context["indicators"] | Record<string, never>;
  national_context: string;
  sources: CityBriefSource[];
  label: string;
  online: boolean;
  trajectory: TrajectoryStep[];
}

export interface EquityGroup {
  group: string;
  homeless_share_pct: number;
  population_share_pct: number;
  disproportionality: number;
  unsheltered_rate_pct: number;
}
export interface Equity {
  coc: string;
  name: string;
  homeless_total: number;
  groups: EquityGroup[];
  most_overrepresented: { group: string; factor: number };
  source: string;
}

export interface ChartCatalogItem {
  name: string;
  kind: string;
  intent: string;
  when: string;
}

export interface ChartSeries {
  name: string;
  color?: string;
  x?: (number | string)[];
  y?: (number | string)[];
  y_lo?: (number | null)[];
  y_hi?: (number | null)[];
  conf?: string[];
  points?: Array<Record<string, number | string | boolean>>;
  // redesign extras:
  base?: number[];                 // waterfall: per-step floor (floating slice)
  measure?: string[];              // waterfall: absolute | relative | total
  colors?: string[];               // explicit per-bar colors (roi, people_helped)
  highlight?: boolean[];           // HBar: which row is the selected city
  robust?: boolean[];              // delta bars: range excludes $0
  abs_total?: number[];            // delta bars: absolute totals for the tooltip
  ref_total?: number;
  raw?: string[];                  // tornado: the raw engine label (for the tooltip)
  tighten_first?: boolean[];       // tornado: high-impact + low-confidence rows
}
export interface HowToRead { plain: string; analogy?: string; tech?: string }
export interface ChartSpec {
  name: string;
  kind: string;
  title: string;
  subtitle?: string;
  x_label?: string;
  y_label?: string;
  series: ChartSeries[];
  horizontal?: boolean;
  annotations?: any[];
  caption?: string;
  source?: string;
  // redesign extras:
  how_to_read?: HowToRead;
  delta?: boolean;                 // scenario_costs: signed delta-from-act-now mode
  no_best?: boolean;               // VBar: don't highlight the lowest bar as "best"
  gap?: { from: number; to: number; value: number; label: string };  // people_helped bracket
  break_even_year?: number | null;
  ratio?: number;
  net_musd?: number;
  pass?: boolean;                  // backtest: observed inside the predicted band
  x_unit?: string;                 // backtest: axis unit label
  trend?: { x0: number; y0: number; x1: number; y1: number };  // scatter trend line
  residual?: number | null;        // scatter: selected city vs the trend
}

export interface ScenarioBand {
  year: number[];
  p10: number[];
  p50: number[];
  p90: number[];
}
export interface ScenarioSummary {
  scenario: string;
  cum_cost_p50_musd: number;
  cum_cost_p10_musd: number;
  cum_cost_p90_musd: number;
  active_homeless: number;
}
export interface ScenarioPayload {
  budget_musd: number;
  delay_years: number;
  scenarios: ScenarioSummary[];
  bands: { status_quo: ScenarioBand; act_now: ScenarioBand; delay: ScenarioBand };
  divergence?: {
    years: number[];
    status_quo: { p10: number[]; p50: number[]; p90: number[] };
    delay: { p10: number[]; p50: number[]; p90: number[] };
  };
  cost_of_waiting_musd: { p50: number; p10: number; p90: number };
  composition?: {
    total_musd: number;
    baseline_musd?: number;
    saves_vs_nothing_musd?: number;
    groups: { key: string; label: string; cost_musd: number; pct: number }[];
  };
}

export interface EffectBand {
  delay_years: number;
  budget_musd: number;
  cow_lo_musd: number;
  cow_base_musd: number;
  cow_hi_musd: number;
  effect_lo: number;
  effect_hi: number;
}

export interface ModelPayload {
  target_coc: string;
  features: string[];
  model: string;
  loo_r2: number;
  loo_mae: number;
  insample_r2: number;
  observed_rate_per_1k: number;
  predicted_rate_per_1k: number;
  shap_target: { feature: string; shap: number }[];
  spm_crossval: {
    spm_inflow_monthly: number;
    ml_inflow_monthly: number;
    agreement_pct_diff: number;
    note: string;
  };
  inflow_at_risk_monthly: { p50: number; p10: number; p90: number };
  data_source: string;
}

export interface Backtest {
  seed_total: number;
  predicted_active_p10: number;
  predicted_active_p50: number;
  predicted_active_p90: number;
  observed_2024_total: number;
  abs_pct_error_p50: number;
  within_band: boolean;
}

export interface CocPoint {
  coc: string;
  name: string;
  lat: number;
  lon: number;
  pit_total: number;
  population: number;
  rate_per_1k: number;
  median_home_value: number;
  highlight: boolean;
}

export interface TrajectoryStep {
  skill: string;
  tier: 0 | 1 | 2;
  approved: boolean;
  detail?: string;   // distinguishes repeated steps (e.g. the 3 Monte-Carlo runs)
}

// The decision agent: a plain-English recommendation synthesized from the scenarios.
export interface Decision {
  verdict: "act_now" | "lean_act_now" | "can_wait" | "review";
  verdict_label: string;
  headline: string;
  plain_summary: string;
  direction_confidence: "high" | "medium" | "low";
  magnitude_note: string;
  evidence: {
    cost_of_waiting_musd: number | null;
    cost_of_waiting_range_musd: [number, number] | null;
    savings_now_musd: number | null;
    break_even_year: number | null;
    baseline_10yr_musd: number | null;
    delay_years: number;
  };
  narrated_by?: string;
}

// The Evaluator agent (5th agent): a per-dimension check of the answer, run before
// the user sees it. status drives the panel: pass (green) / warn (yellow caveats) /
// repair (self-corrected) / decline (refused, with a suggested reformulation).
export interface ResponseCheck {
  status: "pass" | "warn" | "repair" | "decline";
  confidence: "high" | "medium" | "low";
  checks: { name: string; status: "ok" | "warn" | "fail"; detail: string }[];
  what_went_wrong: string[];
  repair_hint: string | null;
  suggested_reformulation: string | null;
}

export interface AskResult {
  declined?: boolean;
  out_of_scope?: boolean;
  greeting?: boolean;
  reason?: string;
  plan?: { intent: string; delay_years: number; budget_musd: number; planner: string;
           param_echo?: string; defaults_used?: string[] };
  intent?: string;
  // Evaluator agent: per-dimension check of the answer before it's shown.
  response_check?: ResponseCheck;
  // Confidence-gated routing: when the routers disagree, the two readings to pick from.
  route_alternatives?: { intent: string; label: string }[];
  repaired?: boolean;
  direct_answer?: string;
  recommended_chart?: string;
  comparison?: any;
  brief_markdown?: string;
  trajectory: TrajectoryStep[];
  coc?: string;
  // City Brief agent (city_situation / care_plan) responses:
  city_brief?: CityBrief;
  label?: string;
  online?: boolean;
  // Decision agent (analytic answers): the plain-English recommendation.
  decision?: Decision;
  // Budget sweep: one cost-of-waiting row per program size (no single hero number).
  sweep?: {
    intent: string;
    delay_years: number;
    rows: {
      budget_musd: number;
      cost_of_waiting: { extra_cost_median: number; extra_cost_p10: number; extra_cost_p90: number } | null;
    }[];
  } | null;
}
