// KpiStrip — a hero row of elevated glass stat cards at the top of the command
// center. Self-contained and presentation-only: it fetches banded risk scores
// (`GET /risk/scores`) once on mount and derives a few headline KPIs from them.
//
// It never breaks the page: while loading it shows a shimmer skeleton row, and
// if the fetch fails it silently renders nothing (the dashboard below is
// unaffected). Data/logic are untouched — this only visualizes existing scores.

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Flame,
  Radar,
  type LucideIcon,
} from "lucide-react";
import { getRiskScores } from "../api";
import { bandLabel, formatScore } from "../lib";
import type { RiskBand, RiskScore } from "../types";

/** Band buckets: low 0–33, elevated 34–66, high 67–100. */
function bandFromScore(score: number): RiskBand {
  if (score >= 67) return "high";
  if (score >= 34) return "elevated";
  return "low";
}

/** Visual treatment (numeric color, thin top accent bar) per band. */
const BAND_STYLE: Record<RiskBand, { num: string; bar: string }> = {
  low: {
    num: "text-emerald-600",
    bar: "bg-emerald-500",
  },
  elevated: {
    num: "text-amber-600",
    bar: "bg-amber-500",
  },
  high: {
    num: "text-rose-600",
    bar: "bg-rose-500",
  },
};

/** Neutral (non-band) treatment for informational counts. */
const NEUTRAL_STYLE = {
  num: "text-sky-600",
  bar: "bg-sky-500",
};

interface Kpi {
  label: string;
  value: string;
  sub: string;
  icon: LucideIcon;
  style: { num: string; bar: string };
}

/** Derive the headline KPIs from the ranked risk scores. */
function deriveKpis(scores: RiskScore[]): Kpi[] {
  const corridors = scores.filter((s) => s.target_type === "corridor");
  const topCorridor = corridors.reduce<RiskScore | null>(
    (top, s) => (top === null || s.score > top.score ? s : top),
    null,
  );
  const highCorridors = corridors.filter((s) => s.band === "high").length;
  const overallScore = scores.reduce((max, s) => Math.max(max, s.score), 0);
  const overallBand = bandFromScore(overallScore);

  return [
    {
      label: "Highest corridor risk",
      value: topCorridor ? formatScore(topCorridor.score) : "—",
      sub: topCorridor ? `${topCorridor.target} · ${bandLabel(topCorridor.band)}` : "no corridors",
      icon: Flame,
      style: BAND_STYLE[topCorridor ? topCorridor.band : "low"],
    },
    {
      label: "Corridors in high band",
      value: String(highCorridors),
      sub: `of ${corridors.length} monitored corridors`,
      icon: AlertTriangle,
      style: highCorridors > 0 ? BAND_STYLE.high : BAND_STYLE.low,
    },
    {
      label: "Targets monitored",
      value: String(scores.length),
      sub: "corridors & supplier countries",
      icon: Radar,
      style: NEUTRAL_STYLE,
    },
    {
      label: "Overall posture",
      value: bandLabel(overallBand),
      sub: scores.length > 0 ? `peak score ${formatScore(overallScore)}` : "awaiting scores",
      icon: Activity,
      style: BAND_STYLE[overallBand],
    },
  ];
}

const container = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

/** A single KPI column inside the shared strip (no per-card box). */
function StatColumn({ kpi }: { kpi: Kpi }) {
  const Icon = kpi.icon;
  return (
    <div className="p-5">
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 shrink-0 ${kpi.style.num}`} aria-hidden />
        <p className="text-[11px] font-medium uppercase tracking-widest text-slate-500">
          {kpi.label}
        </p>
      </div>
      <p
        className={`mt-3 font-mono text-3xl font-bold leading-none tracking-tight ${kpi.style.num}`}
      >
        {kpi.value}
      </p>
      <p className="mt-2 truncate text-xs text-slate-500" title={kpi.sub}>
        {kpi.sub}
      </p>
    </div>
  );
}

/** A single shimmer column matching the KPI column layout. */
function SkeletonColumn() {
  return (
    <div className="p-5">
      <div className="space-y-3">
        <div className="skeleton h-3 w-2/3" />
        <div className="skeleton h-8 w-1/3" />
        <div className="skeleton h-3 w-4/5" />
      </div>
    </div>
  );
}

/** The KPI hero strip. Renders nothing on error so it can never break the page. */
export function KpiStrip({ className }: { className?: string }) {
  const [scores, setScores] = useState<RiskScore[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const res = await getRiskScores();
        if (active) setScores(res.risk_scores);
      } catch {
        if (active) setFailed(true);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Silent fallback: hide the strip entirely if scores could not be loaded.
  if (failed) return null;

  // One clean grouped strip: a single card with columns divided by light rules.
  const strip =
    "grid grid-cols-2 divide-x divide-y divide-slate-200 sm:divide-y-0 md:grid-cols-4";
  const shell = `overflow-hidden rounded-lg border border-slate-200 bg-white shadow-panel ${className ?? ""}`;

  if (loading || scores === null) {
    return (
      <div className={shell} aria-hidden>
        <div className={strip}>
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonColumn key={i} />
          ))}
        </div>
      </div>
    );
  }

  const kpis = deriveKpis(scores);

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className={shell}
      aria-label="Command center headline metrics"
    >
      <div className={strip}>
        {kpis.map((kpi) => (
          <StatColumn key={kpi.label} kpi={kpi} />
        ))}
      </div>
    </motion.div>
  );
}

export default KpiStrip;
