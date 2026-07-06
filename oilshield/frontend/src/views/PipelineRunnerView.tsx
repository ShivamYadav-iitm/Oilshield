// Pipeline Runner View — the Signal-to-Recommendation Pipeline module
// (Requirements 9.1, 9.2, 9.3, 10.5).
//
// A one-click control triggers the end-to-end backend run (`POST /pipeline/run`)
// with an optional scenario id (R9.1). While the single request is in flight the
// four canonical stages (Ingest -> Score -> Simulate -> Recommend) are advanced
// optimistically through the animated Stepper (pending -> active -> done); on
// success every stage is marked done and a compact per-stage result summary is
// shown, on failure the attributable stage is marked errored (R10.5). A
// prominent `Pipeline_Latency` readout is rendered from `result.latency_ms`
// (R9.2), and the cross-module `linked_actions` surfaced for any high-band
// corridor are listed with their recommended scenario and procurement option
// (R9.3).
//
// Self-contained: all data fetching and local state live here, mirroring the
// sibling module views.

import { useCallback, useRef, useState } from "react";
import { AlertTriangle, ArrowRight, Link2, Play, Timer, Workflow } from "lucide-react";
import { runPipeline, ApiError } from "../api";
import {
  Stepper,
  DEFAULT_PIPELINE_STEPS,
  Panel,
  ErrorMessage,
  type Step,
} from "../components";
import { formatLatencyMs, formatScore } from "../lib";
import type { PipelineResult, RiskScore } from "../types";

/**
 * Shape of a `linked_actions` entry (backend returns `list[dict]`). Mirrors the
 * dict built by the Pipeline Orchestrator for each high-band corridor (R9.3).
 */
interface LinkedAction {
  corridor?: string;
  risk_score?: number;
  recommended_scenario_id?: string;
  recommended_option_id?: string | null;
}

/** Ordered stage keys matching `DEFAULT_PIPELINE_STEPS`. */
const STAGE_KEYS = ["ingest", "score", "simulate", "recommend"] as const;

/**
 * Map a backend error `module` to the pipeline stage it belongs to so a failed
 * run can highlight the offending stage. Returns `null` when the module cannot
 * be attributed to a specific stage (e.g. a network failure).
 */
function moduleToStageIndex(module: string): number | null {
  switch (module) {
    case "ingestion":
    case "signals":
      return 0;
    case "risk":
    case "scoring":
      return 1;
    case "scenario":
    case "simulator":
      return 2;
    case "procurement":
    case "recommender":
      return 3;
    default:
      return null;
  }
}

/** A fresh set of steps with every stage pending. */
function pendingSteps(): Step[] {
  return DEFAULT_PIPELINE_STEPS.map((s) => ({ ...s, state: "pending", detail: undefined }));
}

/** Build the per-stage result details shown on the stepper after a run (R9.1). */
function successSteps(result: PipelineResult): Step[] {
  const topRisk = highestRisk(result.risk_scores);
  const topRec = result.recommendations[0];
  const details: Record<string, string | undefined> = {
    ingest: `${result.signals.length} signals`,
    score: topRisk ? `top ${formatScore(topRisk.score)}` : "no scores",
    simulate: result.impact ? "impact ready" : "no scenario",
    recommend: topRec ? `${result.recommendations.length} options` : "no options",
  };
  return DEFAULT_PIPELINE_STEPS.map((s) => ({
    ...s,
    state: "done",
    detail: details[s.key],
  }));
}

/** Highest-scoring risk target, or null when there are none. */
function highestRisk(scores: RiskScore[]): RiskScore | null {
  if (scores.length === 0) return null;
  return [...scores].sort((a, b) => b.score - a.score)[0];
}

/** Read the `linked_actions` records as typed LinkedAction entries. */
function toLinkedActions(records: Record<string, unknown>[]): LinkedAction[] {
  return records as LinkedAction[];
}

/** The Signal-to-Recommendation Pipeline runner. */
export function PipelineRunnerView() {
  const [steps, setSteps] = useState<Step[]>(pendingSteps);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<{ message: string; stage: string | null } | null>(null);
  const [scenarioId, setScenarioId] = useState("");

  // Tracks which stage the optimistic animation currently marks "active" so a
  // failure with an unattributable module still errors a sensible stage.
  const activeIndexRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  /** Trigger the end-to-end pipeline run and animate the stepper (R9.1, R9.2). */
  const handleRun = useCallback(async () => {
    if (running) return;
    setRunning(true);
    setError(null);
    setResult(null);

    // Optimistically drive the stepper: the first stage goes active immediately,
    // then each subsequent stage lights up on a short interval while the single
    // request is in flight. Completed stages fill in green (R9.1).
    activeIndexRef.current = 0;
    setSteps(
      pendingSteps().map((s, i) => (i === 0 ? { ...s, state: "active" } : s)),
    );
    stopTimer();
    timerRef.current = setInterval(() => {
      const next = activeIndexRef.current + 1;
      if (next >= STAGE_KEYS.length) {
        stopTimer();
        return;
      }
      activeIndexRef.current = next;
      setSteps((prev) =>
        prev.map((s, i) => {
          if (i < next) return { ...s, state: "done" };
          if (i === next) return { ...s, state: "active" };
          return s;
        }),
      );
    }, 450);

    const trimmed = scenarioId.trim();
    try {
      const res = await runPipeline(trimmed === "" ? undefined : trimmed);
      stopTimer();
      setResult(res);
      setSteps(successSteps(res));
    } catch (err) {
      stopTimer();
      const message = err instanceof ApiError ? err.message : "Pipeline run failed.";
      const module = err instanceof ApiError ? err.module : "";
      const failingIndex = moduleToStageIndex(module) ?? activeIndexRef.current;
      setError({ message, stage: STAGE_KEYS[failingIndex] ?? null });
      setSteps((prev) =>
        prev.map((s, i) => {
          if (i < failingIndex) return { ...s, state: "done" };
          if (i === failingIndex) return { ...s, state: "error" };
          return { ...s, state: "pending" };
        }),
      );
    } finally {
      setRunning(false);
    }
  }, [running, scenarioId, stopTimer]);

  const linkedActions = result ? toLinkedActions(result.linked_actions) : [];
  const topRisk = result ? highestRisk(result.risk_scores) : null;
  const topRec = result?.recommendations[0] ?? null;
  const impactSummary = result?.impact?.summary ?? null;

  const runButton = (
    <button
      type="button"
      onClick={() => void handleRun()}
      disabled={running}
      className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Play className="h-3.5 w-3.5" aria-hidden />
      {running ? "Running…" : "Run end-to-end pipeline"}
    </button>
  );

  return (
    <Panel
      title="Signal-to-Recommendation Pipeline"
      subtitle="One-click end-to-end run with latency readout"
      icon={Workflow}
      accent="violet"
      motionDelay={0.29}
      actions={runButton}
      ariaLabel="End-to-end pipeline"
      bodyClassName="space-y-5"
    >
      {/* Optional scenario id for the simulate stage (R9.1). */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[220px] flex-1">
          <label
            htmlFor="pipeline-scenario-id"
            className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-500"
          >
            Scenario id (optional)
          </label>
          <input
            id="pipeline-scenario-id"
            type="text"
            value={scenarioId}
            onChange={(e) => setScenarioId(e.target.value)}
            placeholder="defaults to the auto-selected high-band scenario"
            disabled={running}
            className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-accent/50 disabled:opacity-50"
          />
        </div>
      </div>

      {/* Animated stepper: each stage advances as the run progresses (R9.1). */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <Stepper steps={steps} />
      </div>

      {/* Prominent Pipeline_Latency readout (R9.2). */}
      {result && (
        <div className="flex items-center gap-3">
          <Timer className="h-7 w-7 shrink-0 text-accent" aria-hidden />
          <div>
            <p className="text-[10px] uppercase tracking-wide text-slate-500">
              Pipeline latency
            </p>
            <p className="font-mono text-3xl font-bold leading-tight text-accent">
              {formatLatencyMs(result.latency_ms)}
            </p>
          </div>
        </div>
      )}

      {/* Failure surface with the failing stage indicated (R10.5). */}
      {error && (
        <ErrorMessage
          module={error.stage ? `pipeline · ${error.stage}` : "pipeline"}
          message={error.message}
          onRetry={() => void handleRun()}
        />
      )}

      {/* Per-stage result summary shown on a successful run (R9.1). */}
      {result && (
        <div className="grid grid-cols-2 gap-y-4 sm:grid-cols-4 sm:gap-y-0 sm:divide-x sm:divide-slate-200">
          <StageSummary label="Ingest" value={`${result.signals.length}`} unit="signals" />
          <StageSummary
            label="Score"
            value={topRisk ? formatScore(topRisk.score) : "—"}
            unit={topRisk ? `${topRisk.target} · ${topRisk.band}` : "no scores"}
          />
          <StageSummary
            label="Simulate"
            value={impactSummary ? `${Object.keys(impactSummary).length}` : "—"}
            unit={impactSummary ? "end-state metrics" : "no scenario"}
          />
          <StageSummary
            label="Recommend"
            value={topRec ? formatScore(topRec.recommendation_score) : "—"}
            unit={topRec ? `${topRec.supplier_country} · ${topRec.crude_grade}` : "no options"}
          />
        </div>
      )}

      {/* Impact end-state details, when a scenario ran (R9.1). */}
      {impactSummary && Object.keys(impactSummary).length > 0 && (
        <div className="border-t border-slate-100 pt-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Impact end-state</h3>
          <ul className="grid gap-x-8 sm:grid-cols-2" aria-label="Impact end-state">
            {Object.entries(impactSummary).map(([key, value]) => (
              <li
                key={key}
                className="flex items-center justify-between gap-3 border-b border-slate-100 py-2"
              >
                <span className="min-w-0 truncate text-sm text-slate-600">{key}</span>
                <span className="whitespace-nowrap font-mono text-sm text-slate-900">
                  {Number.isFinite(value) ? value.toFixed(2) : "—"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Linked actions for high-band corridors (R9.3). */}
      {result && (
        <div className="border-t border-slate-100 pt-4">
          <div className="mb-3 flex items-center gap-2">
            <Link2 className="h-4 w-4 text-accent" aria-hidden />
            <h3 className="text-sm font-semibold text-slate-900">
              Linked actions — high-band corridors
            </h3>
          </div>
          {linkedActions.length === 0 ? (
            <p className="text-sm text-slate-500">
              No corridors are in the high band; no linked actions were surfaced.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100" aria-label="Linked actions">
              {linkedActions.map((action, index) => (
                <li
                  key={`${action.corridor ?? "corridor"}-${index}`}
                  className="border-l-2 border-rose-400 py-3 pl-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-rose-700">
                      <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                      {action.corridor ?? "Unknown corridor"}
                    </span>
                    {typeof action.risk_score === "number" && (
                      <span className="whitespace-nowrap font-mono text-xs text-rose-700">
                        risk {formatScore(action.risk_score)}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span className="flex items-center gap-1.5">
                      <ArrowRight className="h-3 w-3 text-slate-400" aria-hidden />
                      Scenario:{" "}
                      <code className="font-mono text-slate-700">
                        {action.recommended_scenario_id ?? "—"}
                      </code>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <ArrowRight className="h-3 w-3 text-slate-400" aria-hidden />
                      Procurement:{" "}
                      <code className="font-mono text-slate-700">
                        {action.recommended_option_id ?? "—"}
                      </code>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  );
}

/** A compact stage-result stat (value + unit) shown after a successful run. */
function StageSummary({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="px-4 first:pl-0">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 font-mono text-xl font-bold text-slate-900">{value}</p>
      <p className="mt-0.5 truncate text-[11px] text-slate-500" title={unit}>
        {unit}
      </p>
    </div>
  );
}

export default PipelineRunnerView;
