// Stepper — animated horizontal pipeline progress (Requirements 9.1, 9.2).
//
// Shows the four end-to-end pipeline stages (Ingest -> Score -> Simulate ->
// Recommend) with a per-stage state (pending / active / done / error) and an
// optional latency readout slot. Framer Motion animates state transitions.
// Presentational: stage states and the latency value are supplied by the caller.

import { motion } from "framer-motion";
import { Check, Loader2, X } from "lucide-react";
import { formatLatencyMs } from "../lib";

export type StepState = "pending" | "active" | "done" | "error";

export interface Step {
  key: string;
  label: string;
  state: StepState;
  /** Optional short per-stage detail (e.g. "12 signals"). */
  detail?: string;
}

export interface StepperProps {
  steps: Step[];
  /** Pipeline_Latency in ms; rendered in the readout slot when provided (R9.2). */
  latencyMs?: number;
  className?: string;
}

/** The canonical pipeline stages in order. Callers can start from this. */
export const DEFAULT_PIPELINE_STEPS: Step[] = [
  { key: "ingest", label: "Ingest", state: "pending" },
  { key: "score", label: "Score", state: "pending" },
  { key: "simulate", label: "Simulate", state: "pending" },
  { key: "recommend", label: "Recommend", state: "pending" },
];

const NODE_CLASSES: Record<StepState, string> = {
  pending: "border-slate-300 bg-slate-100 text-slate-400",
  active: "border-accent bg-teal-50 text-accent",
  done: "border-emerald-300 bg-emerald-50 text-emerald-600",
  error: "border-rose-300 bg-rose-50 text-rose-600",
};

const LABEL_CLASSES: Record<StepState, string> = {
  pending: "text-slate-400",
  active: "text-accent",
  done: "text-slate-700",
  error: "text-rose-600",
};

function StepNode({ state, index }: { state: StepState; index: number }) {
  return (
    <motion.span
      initial={false}
      animate={{ scale: state === "active" ? 1.1 : 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold ${NODE_CLASSES[state]}`}
    >
      {state === "done" ? (
        <Check className="h-4 w-4" />
      ) : state === "error" ? (
        <X className="h-4 w-4" />
      ) : state === "active" ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        index + 1
      )}
    </motion.span>
  );
}

/** Animated horizontal stepper with a latency readout slot. */
export function Stepper({ steps, latencyMs, className }: StepperProps) {
  return (
    <div className={className}>
      <div className="flex items-center">
        {steps.map((step, index) => {
          const isLast = index === steps.length - 1;
          const connectorDone = step.state === "done";
          return (
            <div key={step.key} className="flex flex-1 items-center last:flex-none">
              <div className="flex min-w-[72px] flex-col items-center gap-1.5">
                <StepNode state={step.state} index={index} />
                <span className={`text-xs font-medium ${LABEL_CLASSES[step.state]}`}>
                  {step.label}
                </span>
                {step.detail && (
                  <span className="text-[10px] text-slate-500">{step.detail}</span>
                )}
              </div>
              {!isLast && (
                <div className="relative mx-1 h-0.5 flex-1 self-start rounded bg-slate-200" style={{ marginTop: 15 }}>
                  <motion.div
                    initial={false}
                    animate={{ scaleX: connectorDone ? 1 : 0 }}
                    transition={{ duration: 0.4 }}
                    style={{ transformOrigin: "left" }}
                    className="absolute inset-0 rounded bg-emerald-500/70"
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {latencyMs !== undefined && (
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
          <span className="uppercase tracking-wide text-slate-500">Pipeline latency</span>
          <span className="font-mono text-sm text-accent">{formatLatencyMs(latencyMs)}</span>
        </div>
      )}
    </div>
  );
}

export default Stepper;
