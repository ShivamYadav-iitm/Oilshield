// DashboardShell — the single dark-mode layout hosting all modules
// (Requirements 10.1, 10.2, 10.4, 10.5, 4.4).
//
// Owns the top header (product name + tagline), the global Data_Source_Mode
// provenance banner, a global loading/error surface, and named regions for the
// three modules (Risk Radar, Scenario Simulator, Procurement) plus the Pipeline
// runner. Module content is injected via props so the data-fetching views
// (tasks 21-24) can slot in; placeholders render until then.

import type { ReactNode } from "react";
import { Gauge, Radar, Ship, SlidersHorizontal, Workflow } from "lucide-react";
import type { DataSourceMode } from "../types";
import { Panel } from "./Panel";
import { ProvenanceBanner } from "./ProvenanceBanner";
import { LoadingIndicator } from "./LoadingIndicator";
import { ErrorMessage } from "./ErrorMessage";

export interface DashboardShellProps {
  /** Overall data provenance for the global banner (R4.4). */
  dataSourceMode?: DataSourceMode;
  /** Optional per-source provenance breakdown. */
  dataSourceModes?: Record<string, string>;

  /** Optional hero content (e.g. KPI strip) rendered above the module stack. */
  overview?: ReactNode;

  /** Module region content; placeholders render when omitted. */
  riskRadar?: ReactNode;
  scenarioSimulator?: ReactNode;
  procurement?: ReactNode;
  pipeline?: ReactNode;

  /** Global loading surface (e.g. initial bootstrap). */
  globalLoading?: boolean;
  globalLoadingLabel?: string;
  /** Global error surface, shown above the module grid when present. */
  globalError?: { module: string; message: string } | null;
  onRetryGlobal?: () => void;
}

function Placeholder({ label }: { label: string }) {
  return (
    <div className="flex min-h-[220px] items-center justify-center">
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

/** The light command-center chrome and module layout. */
export function DashboardShell({
  dataSourceMode,
  dataSourceModes,
  overview,
  riskRadar,
  scenarioSimulator,
  procurement,
  pipeline,
  globalLoading = false,
  globalLoadingLabel = "Bringing the command center online…",
  globalError = null,
  onRetryGlobal,
}: DashboardShellProps) {
  return (
    <div className="min-h-full bg-surface-950 text-slate-700">
      <header className="relative border-b border-slate-200 bg-gradient-to-b from-white to-surface-950/70 backdrop-blur-xl">
        {/* Thin accent hairline across the very top of the command center. */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent" />
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <Gauge className="h-7 w-7 shrink-0 text-teal-600" aria-hidden />
            <div>
              <h1 className="font-display text-lg font-bold tracking-tight text-slate-900">
                OilShield
              </h1>
              <p className="text-xs text-slate-500">India Energy Resilience Command Center</p>
            </div>
          </div>
        </div>
        {/* Faint accent glow line under the header. */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-accent/25 to-transparent" />
      </header>

      <main className="mx-auto max-w-[1600px] px-6 py-6">
        {/* Global provenance banner (always visible). */}
        <ProvenanceBanner
          mode={dataSourceMode}
          modes={dataSourceModes}
          className="mb-6"
        />

        {globalError && (
          <ErrorMessage
            module={globalError.module}
            message={globalError.message}
            onRetry={onRetryGlobal}
            className="mb-6"
          />
        )}

        {globalLoading ? (
          <Panel className="min-h-[320px]">
            <LoadingIndicator label={globalLoadingLabel} fullHeight />
          </Panel>
        ) : (
          <>
            {/* Hero overview (KPI strip) above the module stack. */}
            {overview && <div className="mb-6">{overview}</div>}

            {/*
              Each module view is self-contained: it renders its own titled Panel
              plus its own loading / module-scoped error surfaces and fetches
              independently (R10.4, R10.5). So a provided region is rendered
              directly here, and the wrapped placeholder Panel is only used as the
              empty-state fallback — avoiding a redundant double-Panel header.

              Layout: the dense modules each own a full-width row so their internal
              splits (map + ranked list, assumption controls + chart, ranked cards)
              get comfortable width. On every breakpoint they stack in a single
              spacious column rather than being squeezed into narrow side-by-side
              columns. The pipeline runner keeps its full-width row at the bottom.
            */}
            <div className="flex flex-col gap-6">
              {riskRadar ?? (
                <Panel
                  title="Live Risk Radar"
                  subtitle="Corridor & supplier risk scores"
                  icon={Radar}
                  accent="rose"
                  ariaLabel="Live Risk Radar"
                  className="min-h-[320px]"
                >
                  <Placeholder label="Risk radar view loads here." />
                </Panel>
              )}

              {scenarioSimulator ?? (
                <Panel
                  title="Disruption Scenario Simulator"
                  subtitle="What-if cascade impacts"
                  icon={SlidersHorizontal}
                  accent="teal"
                  ariaLabel="Disruption Scenario Simulator"
                  className="min-h-[320px]"
                >
                  <Placeholder label="Scenario simulator view loads here." />
                </Panel>
              )}

              {procurement ?? (
                <Panel
                  title="Adaptive Procurement"
                  subtitle="Ranked alternative sources & routes"
                  icon={Ship}
                  accent="emerald"
                  ariaLabel="Adaptive Procurement"
                  className="min-h-[320px]"
                >
                  <Placeholder label="Procurement view loads here." />
                </Panel>
              )}
            </div>

            <div className="mt-6">
              {pipeline ?? (
                <Panel
                  title="Signal-to-Recommendation Pipeline"
                  subtitle="One-click end-to-end run with latency readout"
                  icon={Workflow}
                  accent="violet"
                  ariaLabel="End-to-end pipeline"
                >
                  <Placeholder label="Pipeline runner loads here." />
                </Panel>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default DashboardShell;
