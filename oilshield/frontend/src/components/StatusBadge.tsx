// StatusBadge — renders a risk band as a colored pill (Requirement 10.2).
//
// Presentational only: given a `RiskBand`, it applies the shared band badge
// classes and label from `src/lib`. Optionally shows the numeric score.

import type { RiskBand } from "../types";
import { bandBadgeClasses, bandLabel, formatScore } from "../lib";

export interface StatusBadgeProps {
  band: RiskBand;
  /** Optional 0..100 score rendered next to the label. */
  score?: number;
  /** Visual size. */
  size?: "sm" | "md";
  className?: string;
}

const SIZE_CLASSES: Record<NonNullable<StatusBadgeProps["size"]>, string> = {
  sm: "px-2 py-0.5 text-[10px]",
  md: "px-2.5 py-1 text-xs",
};

/** A rounded status pill colored by risk band (green / amber / red). */
export function StatusBadge({ band, score, size = "md", className }: StatusBadgeProps) {
  const classes = [
    "inline-flex items-center gap-1.5 rounded-full font-semibold uppercase tracking-wide",
    bandBadgeClasses(band),
    SIZE_CLASSES[size],
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes}>
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full bg-current opacity-80"
      />
      {bandLabel(band)}
      {score !== undefined && (
        <span className="font-mono normal-case opacity-90">{formatScore(score)}</span>
      )}
    </span>
  );
}

export default StatusBadge;
