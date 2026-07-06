// Barrel export for shared presentation components.

export { DashboardShell } from "./DashboardShell";
export type { DashboardShellProps } from "./DashboardShell";

export { Panel } from "./Panel";
export type { PanelProps, PanelAccent } from "./Panel";

export { KpiStrip } from "./KpiStrip";

export { ProvenanceBanner, deriveOverallMode } from "./ProvenanceBanner";
export type { ProvenanceBannerProps } from "./ProvenanceBanner";

export { StatusBadge } from "./StatusBadge";
export type { StatusBadgeProps } from "./StatusBadge";

export { Timeline, buildTimeline } from "./Timeline";
export type {
  TimelineProps,
  TimelineItem,
  TimelineItemKind,
  BuildTimelineOptions,
} from "./Timeline";

export { MapPanel } from "./MapPanel";
export type { MapPanelProps, CorridorPolyline, RoutePolyline } from "./MapPanel";

export { Stepper, DEFAULT_PIPELINE_STEPS } from "./Stepper";
export type { StepperProps, Step, StepState } from "./Stepper";

export { LoadingIndicator } from "./LoadingIndicator";
export type { LoadingIndicatorProps } from "./LoadingIndicator";

export { ErrorMessage } from "./ErrorMessage";
export type { ErrorMessageProps } from "./ErrorMessage";
