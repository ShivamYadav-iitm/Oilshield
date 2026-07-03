// LoadingIndicator — small shared spinner used by module loading surfaces
// (Requirement 10.4). Presentational only.

import { Loader2 } from "lucide-react";

export interface LoadingIndicatorProps {
  /** Optional label shown next to the spinner (e.g. "Scoring corridors…"). */
  label?: string;
  /** Center within the available space (fills its container). */
  fullHeight?: boolean;
  className?: string;
}

/** An accessible spinner with an optional label. */
export function LoadingIndicator({
  label = "Loading…",
  fullHeight = false,
  className,
}: LoadingIndicatorProps) {
  const wrapper = [
    "flex items-center justify-center gap-2 text-sm text-slate-400",
    fullHeight ? "h-full min-h-[120px]" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={wrapper} role="status" aria-live="polite">
      <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

export default LoadingIndicator;
