// Timeline — a chronological event rail (Requirements 10.2, 10.3).
//
// Presentational component that renders a single time-ordered list assembled
// from two sources: normalized signal events (absolute ISO timestamps) and
// scenario projection points (relative day offsets). The `buildTimeline`
// helper merges and sorts them ascending so the rendered rail is always in
// chronological order (Requirement 10.3). Keeping the merge in a pure function
// makes the ordering property directly testable.

import { Radio, TrendingDown } from "lucide-react";
import type { ImpactPoint, RiskBand, Signal } from "../types";
import { formatDateTime } from "../lib";
import { StatusBadge } from "./StatusBadge";

/** Which source produced a timeline item. */
export type TimelineItemKind = "signal" | "projection";

/** A normalized, sortable timeline entry. */
export interface TimelineItem {
  id: string;
  kind: TimelineItemKind;
  /** Sort key in epoch milliseconds (ascending = chronological). */
  timestampMs: number;
  /** Human-friendly timestamp / day label. */
  label: string;
  title: string;
  detail?: string;
  /** Optional risk band for a colored badge. */
  band?: RiskBand;
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** Resolve an ISO string to epoch ms, or `null` when unparseable. */
function parseMs(iso: string): number | null {
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? null : ms;
}

export interface BuildTimelineOptions {
  /**
   * Anchor date for day-0 of the scenario projection. Projection point at
   * `day` is placed at `projectionStart + day` days. Defaults to the latest
   * signal timestamp, or `Date.now()` when there are no signals.
   */
  projectionStart?: Date | string;
}

/**
 * Merge signal events and scenario projection points into a single list sorted
 * ascending by time (Requirement 10.3). Pure and deterministic.
 */
export function buildTimeline(
  signals: Signal[],
  projectionPoints: ImpactPoint[],
  options: BuildTimelineOptions = {},
): TimelineItem[] {
  const signalItems: TimelineItem[] = signals.map((s, i) => {
    const ms = parseMs(s.timestamp);
    return {
      id: `signal-${s.id ?? i}`,
      kind: "signal" as const,
      timestampMs: ms ?? 0,
      label: formatDateTime(s.timestamp),
      title: s.target ? `${s.target}` : "Signal",
      detail: s.text_summary,
    };
  });

  // Resolve the projection anchor.
  let anchorMs: number;
  if (options.projectionStart !== undefined) {
    const provided =
      options.projectionStart instanceof Date
        ? options.projectionStart.getTime()
        : parseMs(options.projectionStart);
    anchorMs = provided ?? Date.now();
  } else if (signalItems.length > 0) {
    anchorMs = Math.max(...signalItems.map((s) => s.timestampMs));
  } else {
    anchorMs = Date.now();
  }

  const projectionItems: TimelineItem[] = projectionPoints.map((p, i) => {
    const ms = anchorMs + p.day * MS_PER_DAY;
    return {
      id: `projection-day-${p.day}-${i}`,
      kind: "projection" as const,
      timestampMs: ms,
      label: `Day ${p.day}`,
      title: `Projected impact — day ${p.day}`,
      detail: `Run rate ${p.refinery_run_rate_pct.toFixed(1)}% · Price idx ${p.fuel_price_index.toFixed(
        1,
      )} · SPR ${p.spr_days_of_cover.toFixed(1)}d`,
    };
  });

  return [...signalItems, ...projectionItems].sort((a, b) => a.timestampMs - b.timestampMs);
}

export interface TimelineProps {
  /** Signal events (absolute timestamps). */
  signals?: Signal[];
  /** Scenario projection points (relative day offsets). */
  projectionPoints?: ImpactPoint[];
  /** Anchor date for day-0 of the projection. */
  projectionStart?: Date | string;
  /** Pre-built items; when provided, `signals`/`projectionPoints` are ignored. */
  items?: TimelineItem[];
  /** Shown when the resulting timeline is empty. */
  emptyLabel?: string;
  className?: string;
}

const KIND_ICON = {
  signal: Radio,
  projection: TrendingDown,
} as const;

/** Vertical, chronologically-ordered timeline rail. */
export function Timeline({
  signals = [],
  projectionPoints = [],
  projectionStart,
  items,
  emptyLabel = "No timeline events yet.",
  className,
}: TimelineProps) {
  const resolved = items ?? buildTimeline(signals, projectionPoints, { projectionStart });

  if (resolved.length === 0) {
    return <p className={`text-xs text-slate-500 ${className ?? ""}`}>{emptyLabel}</p>;
  }

  return (
    <ol className={`relative space-y-4 border-l border-surface-600 pl-5 ${className ?? ""}`}>
      {resolved.map((item) => {
        const Icon = KIND_ICON[item.kind];
        return (
          <li key={item.id} className="relative">
            <span
              aria-hidden
              className="absolute -left-[27px] flex h-5 w-5 items-center justify-center rounded-full border border-surface-600 bg-surface-800 text-accent"
            >
              <Icon className="h-3 w-3" />
            </span>
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-200">{item.title}</p>
              <div className="flex items-center gap-2">
                {item.band && <StatusBadge band={item.band} size="sm" />}
                <time className="whitespace-nowrap font-mono text-[11px] text-slate-500">
                  {item.label}
                </time>
              </div>
            </div>
            {item.detail && <p className="mt-0.5 text-xs text-slate-400">{item.detail}</p>}
          </li>
        );
      })}
    </ol>
  );
}

export default Timeline;
