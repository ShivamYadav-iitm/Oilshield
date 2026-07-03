// ErrorMessage — module-scoped error surface (Requirement 10.5).
//
// Renders a per-module error in place of that module's content while sibling
// modules keep their results. Accepts a normalized `{ module, message }` shape.

import { AlertTriangle } from "lucide-react";

export interface ErrorMessageProps {
  /** The module that produced the error (e.g. "risk", "scenario"). */
  module: string;
  /** Human-readable error message. */
  message: string;
  /** Optional retry handler; renders a "Retry" button when provided. */
  onRetry?: () => void;
  className?: string;
}

/** A contained, dark-mode error card scoped to a single module. */
export function ErrorMessage({ module, message, onRetry, className }: ErrorMessageProps) {
  const wrapper = [
    "flex flex-col gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={wrapper} role="alert">
      <div className="flex items-center gap-2 font-semibold text-red-300">
        <AlertTriangle className="h-4 w-4" aria-hidden />
        <span className="uppercase tracking-wide">{module}</span>
      </div>
      <p className="text-red-200/90">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 self-start rounded-md border border-red-400/40 px-3 py-1 text-xs font-medium text-red-100 transition hover:bg-red-500/20"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export default ErrorMessage;
