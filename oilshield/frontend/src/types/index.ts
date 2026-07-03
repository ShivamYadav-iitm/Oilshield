// TypeScript mirrors of the backend data models.
//
// These interfaces mirror the Pydantic/SQLModel shapes defined in the design's
// "Data Models" section one-to-one so the API client and views are type-checked.
// Conventions:
//   - datetime fields are ISO 8601 strings (JSON has no native date type).
//   - enum-like fields use string-literal union types.
//   - `null` is used where the backend model allows `None`.

// ---- Shared enum-like unions ----

/** Whether a target is a shipping corridor or a supplier country. */
export type TargetType = "corridor" | "country";

/** Risk band buckets: low 0-33, elevated 34-66, high 67-100. */
export type RiskBand = "low" | "elevated" | "high";

/** Provenance of ingested data: real feed vs bundled simulated fallback. */
export type DataSourceMode = "live" | "simulated";

// ---- Signals ----

/** Raw, source-provided signal before normalization. */
export interface RawSignal {
  source: string;
  /** ISO 8601 datetime string. */
  timestamp: string;
  text: string;
  /** 0..100, source-provided hint. */
  raw_severity: number;
  /** Corridor/country name if the feed provides one, else null. */
  hinted_target: string | null;
}

/** A normalized signal ready for extraction and scoring. */
export interface Signal {
  id: string;
  source: string;
  /** ISO 8601 datetime string. */
  timestamp: string;
  text_summary: string;
  /** Corridor or supplier-country name. */
  target: string;
  target_type: TargetType;
  /** 0..100. */
  raw_severity: number;
  data_source_mode: DataSourceMode;
}

/** Structured signal produced by the LLM/deterministic extractor. */
export interface ExtractedSignal {
  signal_id: string;
  /** Carried through for traceability (R2.4). */
  source: string;
  /** Carried through for traceability (R2.4). ISO 8601 datetime string. */
  timestamp: string;
  /** null => unclassified. */
  target: string | null;
  target_type: TargetType | null;
  /** e.g. "geopolitical", "sanctions", "logistics". */
  risk_category: string;
  /** 0..100. */
  severity: number;
  /** false => excluded from scoring (R2.2). */
  classified: boolean;
}

// ---- Risk ----

/** Aggregated, banded risk score for a corridor or country. */
export interface RiskScore {
  target: string;
  target_type: TargetType;
  /** 0..100 inclusive (R3.2). */
  score: number;
  /** R3.4. */
  band: RiskBand;
  /** Traceability (R4.3). */
  contributing_signal_ids: string[];
}

// ---- Scenario ----

/** A single tunable assumption feeding the impact cascade. */
export interface ScenarioAssumption {
  /** e.g. "corridor_closure_pct". */
  key: string;
  label: string;
  value: number;
  min_value: number;
  max_value: number;
  adjustable: boolean;
  /** e.g. "%", "kbd", "days". */
  unit: string;
}

/** A predefined disruption scenario and its assumptions. */
export interface Scenario {
  id: string;
  /** e.g. "Strait of Hormuz partial closure". */
  name: string;
  corridor: string;
  assumptions: ScenarioAssumption[];
}

/** One day's projected values in the impact timeline. */
export interface ImpactPoint {
  day: number;
  refinery_run_rate_pct: number;
  fuel_price_index: number;
  /** >= 0 (R6.4). */
  spr_days_of_cover: number;
  gdp_index: number;
}

/** Full deterministic impact projection for a scenario run. */
export interface ImpactResult {
  scenario_id: string;
  /** Displayed alongside results (R6.2). */
  assumptions_used: ScenarioAssumption[];
  /** Over scenario duration (R6.6). */
  timeline: ImpactPoint[];
  /** End-state deltas keyed by metric name. */
  summary: Record<string, number>;
}

/** Serialized user-configured scenario for save/load. */
export interface SavedScenario {
  /** For compatibility checks (R7.3). */
  version: number;
  name: string;
  assumptions: ScenarioAssumption[];
}

// ---- Procurement ----

/** A scored crude procurement option. */
export interface ProcurementOption {
  id: string;
  supplier_country: string;
  crude_grade: string;
  tanker_route: string;
  spot_price_usd_bbl: number;
  /** 0..1. */
  tanker_availability: number;
  /** 0..1 (higher = worse). */
  port_congestion: number;
  /** 0..1 (higher = better). */
  grade_compatibility: number;
  /** 0..100. */
  recommendation_score: number;
  rationale: string;
}

// ---- Pipeline ----

/** Staged results returned by the end-to-end pipeline run. */
export interface PipelineResult {
  signals: Signal[];
  risk_scores: RiskScore[];
  impact: ImpactResult | null;
  recommendations: ProcurementOption[];
  /** Surfaced when a corridor is "high" (R9.3). */
  linked_actions: Record<string, unknown>[];
  /** Pipeline_Latency (R9.2). */
  latency_ms: number;
  data_source_modes: Record<string, string>;
}
