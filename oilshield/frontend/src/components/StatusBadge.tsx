// StatusBadge — renders a risk band as a minimal status indicator (Requirement 10.2).
//
// Presentational only: clean typography in the band's semantic color, with no
// leading dot, no filled background, and no border box. The band label is shown
// in small, letter-spaced uppercase and the optional score in a slightly larger
// bold monospace. Compact, right-alignable, and vertically centered.

import type { RiskBand } from "../types";
import { bandLabel, formatScore } from "../lib";

export interface StatusBadgeProps {
  band: RiskBand;
  /** Optional 0..100 score rendered next to the label. */
  score?: number;
  /** Visual size. */
  size?: "sm" | "md";
  className?: string;
}

/** Band text color (no background, no border). Amber kept readable on white. */
const BAND_TEXT: Record<RiskBand, string> = {
  low: "text-emerald-700",
  elevated: "text-amber-600",
  high: "text-rose-700",
};

/** Font size for the uppercase band label, per size. */
const LABEL_SIZE: Record<NonNullable<StatusBadgeProps["size"]>, string> = {
  sm: "text-[10px]",
  md: "text-[11px]",
};

/** Font size for the monospace score, per size (a touch larger than the label). */
const SCORE_SIZE: Record<NonNullable<StatusBadgeProps["size"]>, string> = {
  sm: "text-xs",
  md: "text-sm",
};

/** A minimal band indicator: label (+ optional score) as clean colored type. */
export function StatusBadge({ band, score, size = "md", className }: StatusBadgeProps) {
  const classes = ["inline-flex items-center gap-1.5", BAND_TEXT[band], className ?? ""]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes}>
      <span className={`font-semibold uppercase tracking-wider ${LABEL_SIZE[size]}`}>
        {bandLabel(band)}
      </span>
      {score !== undefined && (
        <span className={`font-mono font-bold leading-none ${SCORE_SIZE[size]}`}>
          {formatScore(score)}
        </span>
      )}
    </span>
  );
}

export default StatusBadge;
