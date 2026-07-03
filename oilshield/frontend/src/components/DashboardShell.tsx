// DashboardShell — the single dark-mode layout hosting all modules
// (Requirements 10.1, 10.2, 10.4, 10.5, 4.4).
//
// Owns the top header (product name + tagline), the global Data_Source_Mode
// provenance banner, a global loading/error surface, and named regions for the
// three modules (Risk Radar, Scenario Simulator, Procurement) plus the Pipeline
// runner. Module content is injected via props so the data-fetching views
// (tasks 21-24) can slot in; placeholders render until then.

import type { ReactNode } from "react";
import { Activity, Radar, Ship, SlidersHorizontal, Workflow } from "lucide-react";
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

/** The dark-mode command-center chrome and module layout. */
export function DashboardShell({
  dataSourceMode,
  dataSourceModes,
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
    <div className="min-h-full bg-surface-950 text-slate-200">
      <header className="border-b border-surface-700 bg-surface-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <Activity className="h-6 w-6" />
            </span>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-slate-100">OilShield</h1>
              <p className="text-xs text-slate-400">India Energy Resilience Command Center</p>
            </div>
          </div>
          <ProvenanceBanner
            mode={dataSourceMode}
            modes={dataSourceModes}
            className="hidden sm:flex"
          />
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-6 py-6">
        {/* Global provenance banner (always visible, incl. small screens). */}
        <ProvenanceBanner
          mode={dataSourceMode}
          modes={dataSourceModes}
          className="mb-6 sm:hidden"
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
