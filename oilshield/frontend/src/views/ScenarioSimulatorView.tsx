// Scenario Simulator View — the Disruption Scenario Simulator module
// (Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 6.2, 6.6, 7.1, 7.2, 7.3).
//
// On mount it lists predefined scenarios (`GET /scenarios`) and lets the viewer
// pick one (R5.1). The assumptions panel renders each assumption: adjustable
// ones become number inputs + range sliders bounded with min/max/step to the
// assumption's [min_value, max_value] so only valid values can be entered
// client-side (R5.3, R5.4), while non-adjustable assumptions are shown read-only
// (R5.2). A "Run" action posts the overrides (`POST /scenarios/{id}/run`),
// draws a Recharts timeline of projected values across the scenario duration
// (R6.6), and displays the exact assumptions the backend used (R6.2). If the
// backend rejects an out-of-range value it is surfaced inline (R5.5).
//
// Save serializes the configured scenario (`POST /scenarios/save`) and shows the
// returned id (R7.1). Load takes an id, fetches the saved scenario
// (`GET /scenarios/saved/{id}`), and repopulates the assumption values (R7.2);
// a load failure is rendered inline (R7.3).
//
// Self-contained: all data fetching and local state live here.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FlaskConical, Play, Save, FolderOpen } from "lucide-react";
import {
  getScenarios,
  runScenario,
  saveScenario,
  getSavedScenario,
  ApiError,
} from "../api";
import { Panel, LoadingIndicator, ErrorMessage } from "../components";
import type { ImpactResult, Scenario, ScenarioAssumption } from "../types";

/** Overrides keyed by assumption `key` -> numeric value. */
type Overrides = Record<string, number>;

/** A projected metric line drawn on the timeline (R6.6). */
interface MetricLine {
  key: keyof ImpactPointMetrics;
  label: string;
  color: string;
}

/** The numeric metric fields carried by each ImpactPoint. */
interface ImpactPointMetrics {
  refinery_run_rate_pct: number;
  fuel_price_index: number;
  spr_days_of_cover: number;
  gdp_index: number;
}

const METRIC_LINES: MetricLine[] = [
  { key: "refinery_run_rate_pct", label: "Refinery run rate (%)", color: "#38bdf8" },
  { key: "fuel_price_index", label: "Fuel price index", color: "#f59e0b" },
  { key: "spr_days_of_cover", label: "SPR days of cover", color: "#22c55e" },
  { key: "gdp_index", label: "GDP index", color: "#a78bfa" },
];

/**
 * Derive a sensible slider/number step from an assumption's range so users can
 * move across the whole [min, max] in reasonable increments. Uses integer steps
 * for wide ranges and finer decimal steps for narrow ones.
 */
function stepForRange(min: number, max: number): number {
  const span = Math.abs(max - min);
  if (span === 0) return 1;
  if (span >= 100) return 1;
  if (span >= 10) return 0.5;
  if (span >= 1) return 0.1;
  return 0.01;
}

/** Clamp a value into the assumption's valid range (defence for client input). */
function clamp(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, value));
}

/** Build the initial override map from a scenario's assumption defaults. */
function initialOverrides(scenario: Scenario): Overrides {
  const out: Overrides = {};
  for (const a of scenario.assumptions) {
    out[a.key] = a.value;
  }
  return out;
}

/** The Disruption Scenario Simulator module. */
export function ScenarioSimulatorView() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string>("");
  const [overrides, setOverrides] = useState<Overrides>({});

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const [assumptionsUsed, setAssumptionsUsed] = useState<ScenarioAssumption[]>([]);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  const [loadId, setLoadId] = useState("");
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [savedLoadError, setSavedLoadError] = useState<string | null>(null);

  const selected = useMemo(
    () => scenarios.find((s) => s.id === selectedId) ?? null,
    [scenarios, selectedId],
  );

  /** Fetch predefined scenarios (R5.1). */
  const loadScenarios = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await getScenarios();
      setScenarios(res.scenarios);
      // Auto-select the first scenario so the panel is populated.
      if (res.scenarios.length > 0) {
        const first = res.scenarios[0];
        setSelectedId(first.id);
        setOverrides(initialOverrides(first));
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load scenarios.";
      setLoadError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);

  /** Select a scenario and reset its assumption overrides + prior results. */
  const handleSelect = useCallback(
    (id: string) => {
      setSelectedId(id);
      setImpact(null);
      setAssumptionsUsed([]);
      setRunError(null);
      setSavedId(null);
      setSaveError(null);
      const scenario = scenarios.find((s) => s.id === id);
      if (scenario) setOverrides(initialOverrides(scenario));
    },
    [scenarios],
  );

  /** Update one adjustable assumption, clamped to its valid range (R5.4). */
  const handleAssumptionChange = useCallback(
    (assumption: ScenarioAssumption, raw: number) => {
      const next = clamp(raw, assumption.min_value, assumption.max_value);
      setOverrides((prev) => ({ ...prev, [assumption.key]: next }));
    },
    [],
  );

  /** Run the scenario with the current overrides (R6.6, R6.2, R5.5). */
  const handleRun = useCallback(async () => {
    if (!selectedId) return;
    setRunning(true);
    setRunError(null);
    try {
      const res = await runScenario(selectedId, overrides);
      setImpact(res.impact);
      setAssumptionsUsed(res.assumptions_used);
    } catch (err) {
      // Backend range validation errors (R5.5) arrive here as ApiError.
      const message =
        err instanceof ApiError ? err.message : "Failed to run scenario.";
      setRunError(message);
    } finally {
      setRunning(false);
    }
  }, [selectedId, overrides]);

  /** Save the configured scenario and surface the returned id (R7.1). */
  const handleSave = useCallback(async () => {
    if (!selectedId) return;
    setSaving(true);
    setSaveError(null);
    setSavedId(null);
    try {
      const res = await saveScenario(selectedId, overrides);
      setSavedId(res.id);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to save scenario.";
      setSaveError(message);
    } finally {
      setSaving(false);
    }
  }, [selectedId, overrides]);

  /** Load a saved scenario by id and repopulate assumption values (R7.2, R7.3). */
  const handleLoad = useCallback(async () => {
    const id = loadId.trim();
    if (!id) return;
    setLoadingSaved(true);
    setSavedLoadError(null);
    try {
      const res = await getSavedScenario(id);
      const scenario = res.scenario;
      // Merge the loaded scenario into the picker if not already present, then
      // select it and repopulate assumption values from the saved definition.
      setScenarios((prev) =>
        prev.some((s) => s.id === scenario.id) ? prev : [...prev, scenario],
      );
      setSelectedId(scenario.id);
      setOverrides(initialOverrides(scenario));
      setImpact(null);
      setAssumptionsUsed([]);
      setRunError(null);
      setSavedId(null);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load saved scenario.";
      setSavedLoadError(message);
    } finally {
      setLoadingSaved(false);
    }
  }, [loadId]);

  return (
    <Panel
      title="Disruption Scenario Simulator"
      subtitle="Tune assumptions and project the downstream impact"
      icon={FlaskConical}
      ariaLabel="Disruption Scenario Simulator"
      bodyClassName="space-y-4"
    >
      {loading ? (
        <LoadingIndicator label="Loading scenarios…" fullHeight />
      ) : loadError ? (
        <ErrorMessage
          module="scenario"
          message={loadError}
          onRetry={() => void loadScenarios()}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-5">
          {/* Left column: picker + assumptions + save/load controls. */}
          <div className="space-y-4 lg:col-span-2">
            {/* Scenario picker (R5.1). */}
            <div>
              <label
                htmlFor="scenario-picker"
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400"
              >
                Scenario
              </label>
              <select
                id="scenario-picker"
                value={selectedId}
                onChange={(e) => handleSelect(e.target.value)}
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-accent/50"
              >
                {scenarios.length === 0 && <option value="">No scenarios</option>}
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              {selected && (
                <p className="mt-1 text-xs text-slate-500">
                  Corridor: <span className="text-slate-300">{selected.corridor}</span>
                </p>
              )}
            </div>

            {/* Assumptions panel (R5.2, R5.3, R5.4). */}
            {selected && (
              <div className="rounded-lg border border-surface-700 bg-surface-900/40 p-4">
                <h3 className="mb-3 text-sm font-semibold text-slate-100">
                  Assumptions
                </h3>
                <ul className="flex flex-col gap-4" aria-label="Scenario assumptions">
                  {selected.assumptions.map((a) => {
                    const value = overrides[a.key] ?? a.value;
                    const step = stepForRange(a.min_value, a.max_value);
                    return (
                      <li key={a.key}>
                        <div className="flex items-center justify-between gap-3">
                          <label
                            htmlFor={`assumption-${a.key}`}
                            className="text-sm text-slate-200"
                          >
                            {a.label}
                            {a.unit && (
                              <span className="ml-1 text-xs text-slate-500">
                                ({a.unit})
                              </span>
                            )}
                          </label>
                          {a.adjustable ? (
                            <input
                              id={`assumption-${a.key}`}
                              type="number"
                              value={value}
                              min={a.min_value}
                              max={a.max_value}
                              step={step}
                              onChange={(e) =>
                                handleAssumptionChange(a, e.target.valueAsNumber)
                              }
                              className="w-24 rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-right text-sm text-slate-100 outline-none focus:border-accent/50"
                            />
                          ) : (
                            <span
                              className="w-24 rounded-md border border-surface-800 bg-surface-800/60 px-2 py-1 text-right text-sm text-slate-400"
                              aria-label={`${a.label} (read-only)`}
                            >
                              {a.value}
                            </span>
                          )}
                        </div>
                        {a.adjustable ? (
                          <>
                            <input
                              type="range"
                              value={value}
                              min={a.min_value}
                              max={a.max_value}
                              step={step}
                              onChange={(e) =>
                                handleAssumptionChange(a, e.target.valueAsNumber)
                              }
                              aria-label={`${a.label} slider`}
                              className="mt-2 w-full accent-accent"
                            />
                            <div className="mt-0.5 flex justify-between text-[10px] text-slate-500">
                              <span>{a.min_value}</span>
                              <span>{a.max_value}</span>
                            </div>
                          </>
                        ) : (
                          <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-600">
                            Fixed
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ul>

                {/* Run action. */}
                <button
                  type="button"
                  onClick={() => void handleRun()}
                  disabled={running || !selectedId}
                  className="mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-2 text-sm font-medium text-surface-950 transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Play className="h-4 w-4" aria-hidden />
                  {running ? "Running…" : "Run scenario"}
                </button>

                {/* Save / Load controls (R7.1, R7.2, R7.3). */}
                <div className="mt-4 space-y-3 border-t border-surface-700 pt-4">
                  <div>
                    <button
                      type="button"
                      onClick={() => void handleSave()}
                      disabled={saving || !selectedId}
                      className="inline-flex items-center gap-1.5 rounded-md border border-surface-700 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-surface-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Save className="h-3.5 w-3.5" aria-hidden />
                      {saving ? "Saving…" : "Save scenario"}
                    </button>
                    {savedId && (
                      <p className="mt-1.5 text-xs text-slate-400">
                        Saved as{" "}
                        <code className="rounded bg-surface-800 px-1 py-0.5 font-mono text-accent">
                          {savedId}
                        </code>
                      </p>
                    )}
                    {saveError && (
                      <div className="mt-2">
                        <ErrorMessage module="scenario" message={saveError} />
                      </div>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor="load-id"
                      className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-500"
                    >
                      Load saved scenario
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        id="load-id"
                        type="text"
                        value={loadId}
                        onChange={(e) => setLoadId(e.target.value)}
                        placeholder="saved scenario id"
                        className="min-w-0 flex-1 rounded-md border border-surface-700 bg-surface-900 px-2 py-1.5 text-sm text-slate-100 outline-none focus:border-accent/50"
                      />
                      <button
                        type="button"
                        onClick={() => void handleLoad()}
                        disabled={loadingSaved || !loadId.trim()}
                        className="inline-flex items-center gap-1.5 rounded-md border border-surface-700 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-surface-800 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <FolderOpen className="h-3.5 w-3.5" aria-hidden />
                        {loadingSaved ? "Loading…" : "Load"}
                      </button>
                    </div>
                    {savedLoadError && (
                      <div className="mt-2">
                        <ErrorMessage module="scenario" message={savedLoadError} />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right column: run error / timeline / assumptions used. */}
          <div className="space-y-4 lg:col-span-3">
            {runError && (
              <ErrorMessage
                module="scenario"
                message={runError}
                onRetry={() => void handleRun()}
              />
            )}

            {running ? (
              <LoadingIndicator label="Projecting impact…" fullHeight />
            ) : impact ? (
              <>
                {/* Recharts timeline of projected values (R6.6). */}
                <div className="rounded-lg border border-surface-700 bg-surface-900/40 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-slate-100">
                    Projected impact timeline
                  </h3>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={impact.timeline}
                        margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis
                          dataKey="day"
                          stroke="#64748b"
                          tick={{ fontSize: 11 }}
                          label={{
                            value: "Day",
                            position: "insideBottom",
                            offset: -2,
                            fill: "#64748b",
                            fontSize: 11,
                          }}
                        />
                        <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#0f172a",
                            border: "1px solid #334155",
                            borderRadius: 8,
                            fontSize: 12,
                          }}
                          labelStyle={{ color: "#e2e8f0" }}
                          labelFormatter={(d) => `Day ${d}`}
                        />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        {METRIC_LINES.map((m) => (
                          <Line
                            key={m.key}
                            type="monotone"
                            dataKey={m.key}
                            name={m.label}
                            stroke={m.color}
                            dot={false}
                            strokeWidth={2}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Assumptions used, as returned by the backend (R6.2). */}
                <div className="rounded-lg border border-surface-700 bg-surface-900/40 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-slate-100">
                    Assumptions used
                  </h3>
                  {assumptionsUsed.length === 0 ? (
                    <p className="text-sm text-slate-400">
                      No assumptions reported.
                    </p>
                  ) : (
                    <ul
                      className="grid gap-2 sm:grid-cols-2"
                      aria-label="Assumptions used"
                    >
                      {assumptionsUsed.map((a) => (
                        <li
                          key={a.key}
                          className="flex items-center justify-between gap-3 rounded-md border border-surface-700 bg-surface-900/60 px-3 py-2"
                        >
                          <span className="min-w-0 truncate text-sm text-slate-300">
                            {a.label}
                          </span>
                          <span className="whitespace-nowrap font-mono text-sm text-slate-100">
                            {a.value}
                            {a.unit && (
                              <span className="ml-1 text-xs text-slate-500">
                                {a.unit}
                              </span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </>
            ) : (
              <div className="flex h-full min-h-[200px] items-center justify-center rounded-lg border border-dashed border-surface-700 bg-surface-900/20 p-6 text-center">
                <p className="text-sm text-slate-500">
                  Pick a scenario, adjust its assumptions, and run to project the
                  downstream impact.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

export default ScenarioSimulatorView;
