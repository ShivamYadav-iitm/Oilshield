// Procurement View — the Adaptive Procurement Recommendation module
// (Requirements 8.4, 8.5).
//
// On mount it requests ranked procurement options (`POST /procurement/recommend`)
// and renders them as ranked cards ordered highest-to-lowest by
// recommendation_score (R8.4). For each recommended option it shows the spot
// price, tanker availability, port congestion, refinery grade compatibility, and
// a plain-language rationale (R8.5). The top-ranked option (#1) is visually
// highlighted. A "Refresh recommendations" control re-runs the recommender.
//
// Self-contained: all data fetching and local state live here via
// useState/useEffect, mirroring the sibling module views.

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Ship, ShoppingCart } from "lucide-react";
import { recommendProcurement, ApiError } from "../api";
import { Panel, LoadingIndicator, ErrorMessage } from "../components";
import { formatUsd, formatFraction, formatScore } from "../lib";
import type { ProcurementOption } from "../types";

/**
 * Order options highest-to-lowest by recommendation_score (R8.4). The backend
 * already returns them ranked, but we sort defensively so render order always
 * reflects the score regardless of transport quirks.
 */
function rankByScore(options: ProcurementOption[]): ProcurementOption[] {
  return [...options].sort((a, b) => b.recommendation_score - a.recommendation_score);
}

/** A single attribute cell (label + formatted value) inside an option card. */
function Attribute({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-100">{value}</span>
    </div>
  );
}

/** One ranked procurement option card (R8.5); #1 is visually highlighted. */
function OptionCard({ option, rank }: { option: ProcurementOption; rank: number }) {
  const isTop = rank === 1;

  return (
    <li
      className={`rounded-lg border p-4 transition ${
        isTop
          ? "border-accent/50 bg-accent/5 shadow-[0_0_0_1px_rgba(56,189,248,0.15)]"
          : "border-surface-700 bg-surface-900/40"
      }`}
      aria-label={`Rank ${rank}: ${option.supplier_country} ${option.crude_grade}`}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Rank + title (supplier country + crude grade). */}
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={`inline-flex h-7 shrink-0 items-center justify-center rounded-md px-2 text-xs font-semibold ${
              isTop
                ? "bg-accent text-surface-950"
                : "bg-surface-800 text-slate-300"
            }`}
            aria-hidden
          >
            #{rank}
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-slate-100">
              {option.supplier_country}
              <span className="ml-1.5 text-slate-400">· {option.crude_grade}</span>
              {isTop && (
                <span className="ml-2 rounded bg-accent/20 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent">
                  Top pick
                </span>
              )}
            </h3>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-400">
              <Ship className="h-3 w-3" aria-hidden />
              <span className="truncate">{option.tanker_route}</span>
            </p>
          </div>
        </div>

        {/* Recommendation score, shown prominently (R8.4). */}
        <div className="flex shrink-0 flex-col items-center rounded-lg border border-surface-700 bg-surface-900/60 px-3 py-1.5">
          <span className="text-2xl font-bold leading-none text-accent">
            {formatScore(option.recommendation_score)}
          </span>
          <span className="mt-0.5 text-[9px] uppercase tracking-wide text-slate-500">
            score
          </span>
        </div>
      </div>

      {/* Attribute grid: spot price + the three 0..1 fractions (R8.5). */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Attribute label="Spot price / bbl" value={formatUsd(option.spot_price_usd_bbl)} />
        <Attribute
          label="Tanker availability"
          value={formatFraction(option.tanker_availability)}
        />
        <Attribute
          label="Port congestion"
          value={formatFraction(option.port_congestion)}
        />
        <Attribute
          label="Grade compatibility"
          value={formatFraction(option.grade_compatibility)}
        />
      </div>

      {/* Plain-language rationale (R8.5). */}
      <p className="mt-3 border-t border-surface-800 pt-3 text-sm text-slate-300">
        {option.rationale}
      </p>
    </li>
  );
}

/** The Adaptive Procurement Recommendation module. */
export function ProcurementView() {
  const [options, setOptions] = useState<ProcurementOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /** Request ranked procurement options (R8.4, R8.5). */
  const loadRecommendations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await recommendProcurement();
      setOptions(res.recommendations);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load procurement recommendations.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRecommendations();
  }, [loadRecommendations]);

  const ranked = useMemo(() => rankByScore(options), [options]);

  const refreshButton = (
    <button
      type="button"
      onClick={() => void loadRecommendations()}
      disabled={loading}
      className="inline-flex items-center gap-1.5 rounded-md border border-surface-700 px-3 py-1 text-xs font-medium text-slate-200 transition hover:bg-surface-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <RefreshCw
        className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
        aria-hidden
      />
      {loading ? "Refreshing…" : "Refresh recommendations"}
    </button>
  );

  return (
    <Panel
      title="Adaptive Procurement"
      subtitle="Ranked alternative crude sources & tanker routes"
      icon={ShoppingCart}
      actions={refreshButton}
      ariaLabel="Adaptive Procurement Recommendation"
      bodyClassName="space-y-4"
    >
      {loading ? (
        <LoadingIndicator label="Ranking procurement options…" fullHeight />
      ) : error ? (
        <ErrorMessage
          module="procurement"
          message={error}
          onRetry={() => void loadRecommendations()}
        />
      ) : ranked.length === 0 ? (
        <div className="flex min-h-[160px] items-center justify-center rounded-lg border border-dashed border-surface-700 bg-surface-900/20 p-6 text-center">
          <p className="text-sm text-slate-500">
            No procurement options met the recommendation criteria.
          </p>
        </div>
      ) : (
        <ol className="flex flex-col gap-3" aria-label="Ranked procurement options">
          {ranked.map((option, index) => (
            <OptionCard key={option.id} option={option} rank={index + 1} />
          ))}
        </ol>
      )}
    </Panel>
  );
}

export default ProcurementView;
