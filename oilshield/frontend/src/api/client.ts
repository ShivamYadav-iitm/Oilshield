// Typed API client for the OilShield backend.
//
// A thin `fetch` wrapper with one function per backend endpoint. Response shapes
// mirror the backend models (see `src/types`). Every non-OK response is parsed
// from the backend error envelope `{ error: { module, message, code } }` and
// re-thrown as a normalized `ApiError` carrying `{ module, message }` so views
// can render per-module errors (Requirement 10.5).

import type {
  ImpactResult,
  PipelineResult,
  ProcurementOption,
  RiskScore,
  Scenario,
  ScenarioAssumption,
  Signal,
} from "../types";

/**
 * Base URL for the backend API.
 *
 * Configurable via the `VITE_API_BASE` environment variable. Defaults to the
 * local FastAPI server. The client calls the backend directly using this base
 * (e.g. `${API_BASE}/pipeline/run`). In development the Vite dev server also
 * proxies `/api` -> `http://localhost:8000`; to route through that proxy
 * instead, set `VITE_API_BASE=/api`.
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

/** Shape of the backend error envelope: `{ error: { module, message, code } }`. */
interface ErrorEnvelope {
  error?: {
    module?: string;
    message?: string;
    code?: string;
  };
}

/**
 * Normalized client-side error. Every failed request rejects with an `ApiError`
 * exposing `module` and `message` so callers never have to parse the envelope.
 */
export class ApiError extends Error {
  /** The backend module that produced the error (e.g. "ingestion", "scenario"). */
  readonly module: string;
  /** HTTP status code, when the failure came from a response. */
  readonly status?: number;
  /** Backend error code, when provided in the envelope. */
  readonly code?: string;

  constructor(params: { module: string; message: string; status?: number; code?: string }) {
    super(params.message);
    this.name = "ApiError";
    this.module = params.module;
    this.status = params.status;
    this.code = params.code;
    // Restore prototype chain for `instanceof` under transpiled targets.
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

/** Public, minimal normalized error shape `{ module, message }` (Requirement 10.5). */
export interface NormalizedError {
  module: string;
  message: string;
}

/** Build a full request URL from a path, encoding is the caller's responsibility. */
function url(path: string): string {
  return `${API_BASE}${path}`;
}

/**
 * Core request helper. Sends JSON, parses JSON, and normalizes any failure
 * (non-OK status, network error, or unparseable body) into an `ApiError`.
 */
async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const { method = "GET", body } = options;

  let response: Response;
  try {
    response = await fetch(url(path), {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    // Network / CORS / DNS failure — no response was received.
    throw new ApiError({
      module: "network",
      message: err instanceof Error ? err.message : "Network request failed",
    });
  }

  if (!response.ok) {
    throw await normalizeErrorResponse(response);
  }

  // 204 No Content or empty body — return undefined cast to T.
  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError({
      module: "network",
      message: "Failed to parse response body as JSON",
      status: response.status,
    });
  }
}

/** Parse a non-OK response into a normalized `ApiError` using the error envelope. */
async function normalizeErrorResponse(response: Response): Promise<ApiError> {
  let envelope: ErrorEnvelope | null = null;
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    envelope = null;
  }

  const err = envelope?.error;
  return new ApiError({
    module: err?.module ?? "api",
    message: err?.message ?? `Request failed with status ${response.status}`,
    status: response.status,
    code: err?.code,
  });
}

// ---- Response types (mirror backend endpoint payloads) ----

export interface RefreshSignalsResponse {
  signals: Signal[];
  data_source_modes: Record<string, string>;
}

export interface RiskScoresResponse {
  risk_scores: RiskScore[];
  data_source_modes: Record<string, string>;
}

export interface TargetSignalsResponse {
  target: string;
  signals: Signal[];
  data_source_modes: Record<string, string>;
}

export interface ScenariosResponse {
  scenarios: Scenario[];
}

export interface RunScenarioResponse {
  impact: ImpactResult;
  assumptions_used: ScenarioAssumption[];
}

export interface SaveScenarioResponse {
  id: string;
}

export interface SavedScenarioResponse {
  scenario: Scenario;
}

export interface RecommendResponse {
  recommendations: ProcurementOption[];
}

// ---- Request bodies ----

/** Assumption overrides keyed by assumption `key` -> value. */
export type AssumptionOverrides = Record<string, number>;

// ---- Endpoint functions ----

/** `POST /signals/refresh` — run ingestion; returns normalized signals + provenance. */
export function refreshSignals(): Promise<RefreshSignalsResponse> {
  return request<RefreshSignalsResponse>("/signals/refresh", { method: "POST" });
}

/** `GET /risk/scores` — banded, ranked risk scores for corridors and countries. */
export function getRiskScores(): Promise<RiskScoresResponse> {
  return request<RiskScoresResponse>("/risk/scores");
}

/** `GET /risk/{target}/signals` — contributing signals for a corridor/country. */
export function getTargetSignals(target: string): Promise<TargetSignalsResponse> {
  return request<TargetSignalsResponse>(`/risk/${encodeURIComponent(target)}/signals`);
}

/** `GET /scenarios` — list predefined scenarios with their assumptions. */
export function getScenarios(): Promise<ScenariosResponse> {
  return request<ScenariosResponse>("/scenarios");
}

/** `POST /scenarios/{id}/run` — validate assumptions and compute the impact result. */
export function runScenario(
  id: string,
  assumptions?: AssumptionOverrides,
): Promise<RunScenarioResponse> {
  return request<RunScenarioResponse>(`/scenarios/${encodeURIComponent(id)}/run`, {
    method: "POST",
    body: { assumptions },
  });
}

/** `POST /scenarios/save` — serialize and store a configured scenario. */
export function saveScenario(
  id: string,
  assumptions?: AssumptionOverrides,
): Promise<SaveScenarioResponse> {
  return request<SaveScenarioResponse>("/scenarios/save", {
    method: "POST",
    body: { id, assumptions },
  });
}

/** `GET /scenarios/saved/{id}` — load a previously saved scenario. */
export function getSavedScenario(id: string): Promise<SavedScenarioResponse> {
  return request<SavedScenarioResponse>(`/scenarios/saved/${encodeURIComponent(id)}`);
}

/** `POST /procurement/recommend` — generate, score, filter, and rank options. */
export function recommendProcurement(): Promise<RecommendResponse> {
  return request<RecommendResponse>("/procurement/recommend", { method: "POST" });
}

/** `POST /pipeline/run` — run the full pipeline; returns staged results + latency. */
export function runPipeline(scenarioId?: string): Promise<PipelineResult> {
  return request<PipelineResult>("/pipeline/run", {
    method: "POST",
    body: { scenario_id: scenarioId },
  });
}
