// Risk Radar View — the live risk module (Requirements 3.5, 4.1, 4.2, 4.3, 4.4).
//
// Fetches banded, ranked risk scores from `/risk/scores`, draws each known
// shipping corridor as a band-colored Leaflet polyline (R4.1), lists corridors
// and supplier countries ranked highest-to-lowest with a status badge and score
// (R4.2), and lets the viewer open any target to see the contributing signals —
// each with its source and timestamp (R4.3) — via `/risk/{target}/signals`.
//
// A Refresh control re-runs ingestion (`/signals/refresh`) and re-fetches scores
// so bands update on new signals (R3.5). Data provenance (live vs simulated) is
// surfaced through the shared ProvenanceBanner from `data_source_modes` (R4.4).
//
// Self-contained: all data fetching lives here via useState/useEffect. The map
// needs concrete geometry, which the risk API does not carry, so corridor
// polylines are defined statically below (coordinates mirror
// `backend/app/data/corridors.json`) and colored per their live RiskScore band.

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Radar } from "lucide-react";
import {
  getRiskScores,
  getTargetSignals,
  refreshSignals,
  ApiError,
} from "../api";
import {
  MapPanel,
  StatusBadge,
  Panel,
  LoadingIndicator,
  ErrorMessage,
  ProvenanceBanner,
  type CorridorPolyline,
} from "../components";
import { formatDateTime } from "../lib";
import type { RiskScore, Signal } from "../types";

/**
 * Static corridor geometry keyed by the corridor's display name (which matches
 * `RiskScore.target` for corridor targets). Coordinates mirror
 * `backend/app/data/corridors.json`. The band is supplied at render time from
 * the live RiskScore so the polyline color always reflects current risk (R4.1).
 */
const CORRIDOR_GEOMETRY: Record<string, [number, number][]> = {
  "Strait of Hormuz": [
    [26.9667, 56.5333],
    [26.7333, 56.4667],
    [26.5665, 56.2497],
    [26.3, 56.1],
    [25.9667, 56.9],
  ],
  "Red Sea": [
    [12.5833, 43.3333],
    [15.5, 41.8],
    [19.5, 38.5],
    [24.5, 35.5],
    [27.9, 33.7],
    [29.9668, 32.5498],
  ],
  "Cape of Good Hope": [
    [4.5, 6.5],
    [-6.0, 11.0],
    [-20.0, 14.0],
    [-34.3587, 18.4736],
    [-33.0, 27.0],
    [-20.0, 40.0],
    [-6.0, 52.0],
  ],
};

/** Sort risk scores highest-to-lowest by score (R4.2). */
function rankByScore(scores: RiskScore[]): RiskScore[] {
  return [...scores].sort((a, b) => b.score - a.score);
}

/** Build band-colored corridor polylines for every corridor score with geometry. */
function toCorridorPolylines(scores: RiskScore[]): CorridorPolyline[] {
  return scores
    .filter((s) => s.target_type === "corridor" && CORRIDOR_GEOMETRY[s.target])
    .map((s) => ({
      id: s.target,
      name: s.target,
      positions: CORRIDOR_GEOMETRY[s.target],
      band: s.band,
    }));
}

/** State for the per-target contributing-signals detail drawer. */
interface DetailState {
  target: string;
  loading: boolean;
  signals: Signal[];
  error: string | null;
}

/** The Live Risk Radar module: map + ranked list + detail drawer + provenance. */
export function RiskRadarView() {
  const [scores, setScores] = useState<RiskScore[]>([]);
  const [modes, setModes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [detail, setDetail] = useState<DetailState | null>(null);

  /** Fetch banded, ranked risk scores plus provenance modes. */
  const loadScores = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getRiskScores();
      setScores(res.risk_scores);
      setModes(res.data_source_modes ?? {});
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load risk scores.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadScores();
  }, [loadScores]);

  /** Re-run ingestion then re-fetch scores so bands update on new signals (R3.5). */
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      await refreshSignals();
      await loadScores();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to refresh signals.";
      setError(message);
    } finally {
      setRefreshing(false);
    }
  }, [loadScores]);

  /** Open a target's detail drawer and fetch its contributing signals (R4.3). */
  const handleSelectTarget = useCallback(async (target: string) => {
    setDetail({ target, loading: true, signals: [], error: null });
    try {
      const res = await getTargetSignals(target);
      setDetail({ target, loading: false, signals: res.signals, error: null });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load contributing signals.";
      setDetail({ target, loading: false, signals: [], error: message });
    }
  }, []);

  const ranked = useMemo(() => rankByScore(scores), [scores]);
  const corridors = useMemo(() => toCorridorPolylines(scores), [scores]);

  const refreshButton = (
    <button
      type="button"
      onClick={() => void handleRefresh()}
      disabled={refreshing || loading}
      className="inline-flex items-center gap-1.5 rounded-md border border-surface-700 px-3 py-1 text-xs font-medium text-slate-200 transition hover:bg-surface-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <RefreshCw
        className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
        aria-hidden
      />
      {refreshing ? "Refreshing…" : "Refresh"}
    </button>
  );

  return (
    <Panel
      title="Live Risk Radar"
      subtitle="Corridor & supplier-country risk by band"
      icon={Radar}
      actions={refreshButton}
      ariaLabel="Live Risk Radar"
      bodyClassName="space-y-4"
    >
      {/* Provenance banner (R4.4). */}
      <ProvenanceBanner modes={modes} />

      {loading ? (
        <LoadingIndicator label="Scoring corridors…" fullHeight />
      ) : error ? (
        <ErrorMessage module="risk" message={error} onRetry={() => void loadScores()} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-5">
          {/* Map with band-colored corridor polylines (R4.1). */}
          <div className="lg:col-span-3">
            <MapPanel corridors={corridors} height={400} />
          </div>

          {/* Ranked list of corridors + countries, highest-to-lowest (R4.2). */}
          <div className="lg:col-span-2">
            {ranked.length === 0 ? (
              <p className="text-sm text-slate-400">No risk scores available.</p>
            ) : (
              <ul className="flex flex-col gap-1.5" aria-label="Ranked risk targets">
                {ranked.map((s) => {
                  const isActive = detail?.target === s.target;
                  return (
                    <li key={`${s.target_type}:${s.target}`}>
                      <button
                        type="button"
                        onClick={() => void handleSelectTarget(s.target)}
                        aria-pressed={isActive}
                        className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition ${
                          isActive
                            ? "border-accent/50 bg-surface-800"
                            : "border-surface-700 bg-surface-900/40 hover:bg-surface-800/60"
                        }`}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium text-slate-100">
                            {s.target}
                          </span>
                          <span className="text-[10px] uppercase tracking-wide text-slate-500">
                            {s.target_type}
                          </span>
                        </span>
                        <StatusBadge band={s.band} score={s.score} size="sm" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Detail drawer: contributing signals with source + timestamp (R4.3). */}
      {detail && (
        <div className="rounded-lg border border-surface-700 bg-surface-900/40 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-slate-100">
              Contributing signals — {detail.target}
            </h3>
            <button
              type="button"
              onClick={() => setDetail(null)}
              className="rounded-md border border-surface-700 px-2 py-0.5 text-xs text-slate-300 transition hover:bg-surface-800"
            >
              Close
            </button>
          </div>

          {detail.loading ? (
            <LoadingIndicator label="Loading contributing signals…" />
          ) : detail.error ? (
            <ErrorMessage
              module="risk"
              message={detail.error}
              onRetry={() => void handleSelectTarget(detail.target)}
            />
          ) : detail.signals.length === 0 ? (
            <p className="text-sm text-slate-400">
              No contributing signals for this target.
            </p>
          ) : (
            <ul className="flex flex-col gap-2" aria-label="Contributing signals">
              {detail.signals.map((sig) => (
                <li
                  key={sig.id}
                  className="rounded-md border border-surface-700 bg-surface-900/60 p-3"
                >
                  <p className="text-sm text-slate-200">{sig.text_summary}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                    <span className="font-medium text-slate-400">{sig.source}</span>
                    <span aria-hidden>•</span>
                    <time dateTime={sig.timestamp}>{formatDateTime(sig.timestamp)}</time>
                    <span aria-hidden>•</span>
                    <span className="font-mono">severity {sig.raw_severity}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  );
}

export default RiskRadarView;
