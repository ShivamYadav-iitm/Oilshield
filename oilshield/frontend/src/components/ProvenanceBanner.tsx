// ProvenanceBanner — global Data_Source_Mode provenance banner (Requirement 4.4).
//
// Surfaces whether the data on screen came from a live feed or the bundled
// simulated fallback, so a viewer always knows the provenance. Can optionally
// break the mode down per source (e.g. { news: "simulated", prices: "live" }).

import { Database, Wifi } from "lucide-react";
import type { DataSourceMode } from "../types";

export interface ProvenanceBannerProps {
  /** Overall mode. If omitted, it is derived from `modes`. */
  mode?: DataSourceMode;
  /** Optional per-source modes; any "simulated" source makes the overall simulated. */
  modes?: Record<string, string>;
  className?: string;
}

/** Reduce a per-source mode map to a single overall mode. */
export function deriveOverallMode(modes: Record<string, string>): DataSourceMode {
  const values = Object.values(modes);
  if (values.length === 0) return "simulated";
  return values.every((m) => m === "live") ? "live" : "simulated";
}

/** A slim banner announcing the live vs simulated provenance of the data. */
export function ProvenanceBanner({ mode, modes, className }: ProvenanceBannerProps) {
  const overall: DataSourceMode = mode ?? (modes ? deriveOverallMode(modes) : "simulated");
  const isLive = overall === "live";
  const Icon = isLive ? Wifi : Database;

  // Solid dark navy blue strip for both states; only the accent color of the
  // status label/icon changes to still signal live (emerald) vs simulated (amber).
  const labelTone = isLive ? "text-emerald-300" : "text-amber-300";

  return (
    <div
      role="status"
      className={`flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-white/10 bg-[#0F2A4A] px-4 py-2 text-xs text-slate-100 ${className ?? ""}`}
    >
      <span className={`flex items-center gap-2 font-semibold uppercase tracking-wide ${labelTone}`}>
        <Icon className="h-4 w-4" aria-hidden />
        {isLive ? "Live data" : "Simulated data"}
      </span>
      <span className="text-slate-300">
        {isLive
          ? "Showing signals from live feeds."
          : "Showing bundled simulated data — external feeds unavailable or disabled."}
      </span>
      {modes && Object.keys(modes).length > 0 && (
        <span className="ml-auto font-mono text-[10px] text-slate-400">
          {Object.entries(modes).map(([source, m], index) => (
            <span key={source}>
              {index > 0 && <span className="text-slate-600"> · </span>}
              <span className="text-slate-300">{source}</span>
              <span className="text-slate-500">: </span>
              <span className={m === "live" ? "text-emerald-300" : "text-amber-300"}>{m}</span>
            </span>
          ))}
        </span>
      )}
    </div>
  );
}

export default ProvenanceBanner;
