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
import { motion } from "framer-motion";
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
      <span className="text-sm font-medium text-slate-900">{value}</span>
    </div>
  );
}

/**
 * An attribute with a slim colored progress bar beneath the value. `fraction`
 * (0..1) drives the bar width; `tone` picks the fill color. Purely visual — the
 * underlying values are unchanged.
 */
function AttributeBar({
  label,
  value,
  fraction,
  tone,
}: {
  label: string;
  value: string;
  fraction: number;
  tone: "emerald" | "amber" | "sky";
}) {
  const pct = Math.max(0, Math.min(1, fraction)) * 100;
  const fill =
    tone === "emerald"
      ? "bg-emerald-500"
      : tone === "amber"
        ? "bg-amber-500"
        : "bg-sky-500";
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-900">{value}</span>
      <span className="mt-0.5 block h-1 w-full overflow-hidden rounded-full bg-slate-100">
        <span className={`block h-full rounded-full ${fill}`} style={{ width: `${pct}%` }} />
      </span>
    </div>
  );
}

/** Radial score ring (SVG circular progress) showing recommendation_score/100. */
function RadialScore({ score }: { score: number }) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(100, score));
  const offset = circumference * (1 - pct / 100);
  return (
    <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
      <svg className="h-20 w-20 -rotate-90" viewBox="0 0 64 64" aria-hidden>
        <defs>
          <linearGradient id="proc-score-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#10B981" />
            <stop offset="100%" stopColor="#0D9488" />
          </linearGradient>
        </defs>
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="6"
          className="stroke-slate-200"
        />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          stroke="url(#proc-score-ring)"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="font-mono text-xl font-bold leading-none text-slate-900">
          {formatScore(score)}
        </span>
        <span className="text-[8px] uppercase tracking-widest text-slate-500">score</span>
      </div>
    </div>
  );
}

const cardItem = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] } },
};

/** One ranked procurement option row (R8.5); #1 gets a left accent bar. */
function OptionCard({ option, rank }: { option: ProcurementOption; rank: number }) {
  const isTop = rank === 1;

  return (
    <motion.li
      variants={cardItem}
      className={`py-4 pl-3 border-l-2 ${
        isTop ? "border-emerald-500" : "border-transparent"
      }`}
      aria-label={`Rank ${rank}: ${option.supplier_country} ${option.crude_grade}`}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Rank + title (supplier country + crude grade). */}
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={`shrink-0 text-sm font-semibold ${
              isTop ? "text-emerald-600" : "text-slate-400"
            }`}
            aria-hidden
          >
            #{rank}
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-slate-900">
              {option.supplier_country}
              <span className="ml-1.5 text-slate-500">· {option.crude_grade}</span>
              {isTop && (
                <span className="ml-2 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                  Top pick
                </span>
              )}
            </h3>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
              <Ship className="h-3 w-3" aria-hidden />
              <span className="truncate">{option.tanker_route}</span>
            </p>
          </div>
        </div>

        {/* Recommendation score (R8.4): a radial ring for the top pick, a clean
            prominent number for the rest. */}
        {isTop ? (
          <RadialScore score={option.recommendation_score} />
        ) : (
          <div className="flex shrink-0 flex-col items-center">
            <span className="font-mono text-2xl font-bold leading-none text-emerald-600">
              {formatScore(option.recommendation_score)}
            </span>
            <span className="mt-0.5 text-[9px] uppercase tracking-wide text-slate-500">
              score
            </span>
          </div>
        )}
      </div>

      {/* Attribute grid: spot price + the three 0..1 fractions with bars (R8.5). */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Attribute label="Spot price / bbl" value={formatUsd(option.spot_price_usd_bbl)} />
        <AttributeBar
          label="Tanker availability"
          value={formatFraction(option.tanker_availability)}
          fraction={option.tanker_availability}
          tone="emerald"
        />
        <AttributeBar
          label="Port congestion"
          value={formatFraction(option.port_congestion)}
          fraction={1 - option.port_congestion}
          tone="amber"
        />
        <AttributeBar
          label="Grade compatibility"
          value={formatFraction(option.grade_compatibility)}
          fraction={option.grade_compatibility}
          tone="sky"
        />
      </div>

      {/* Plain-language rationale (R8.5). */}
      <p className="mt-3 text-sm text-slate-600">{option.rationale}</p>
    </motion.li>
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
      className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
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
      accent="emerald"
      motionDelay={0.21}
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
        <div className="flex min-h-[160px] items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
          <p className="text-sm text-slate-500">
            No procurement options met the recommendation criteria.
          </p>
        </div>
      ) : (
        <motion.ol
          className="divide-y divide-slate-100"
          aria-label="Ranked procurement options"
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.07 } } }}
        >
          {ranked.map((option, index) => (
            <OptionCard key={option.id} option={option} rank={index + 1} />
          ))}
        </motion.ol>
      )}
    </Panel>
  );
}

export default ProcurementView;
