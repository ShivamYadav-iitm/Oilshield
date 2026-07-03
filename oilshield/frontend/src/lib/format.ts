// Shared presentation helpers used by badges, the map, and charts.
//
// Includes the band-to-color mapping (Requirement 4.1: corridors are drawn with a
// color that corresponds to their status band) plus small formatting utilities so
// numeric values render consistently across the dashboard.

import type { RiskBand } from "../types";

// ---- Band-to-color helpers (Requirement 4.1) ----

/**
 * Hex color per risk band. Used for raw color contexts such as Leaflet polylines
 * and Recharts strokes/fills that need a concrete color rather than a CSS class.
 *
 *   low      -> green
 *   elevated -> amber
 *   high     -> red
 */
export const BAND_HEX: Record<RiskBand, string> = {
  low: "#22c55e", // tailwind green-500
  elevated: "#f59e0b", // tailwind amber-500
  high: "#ef4444", // tailwind red-500
};

/** Return the hex color for a risk band (green / amber / red). */
export function bandColor(band: RiskBand): string {
  return BAND_HEX[band];
}

/**
 * Tailwind utility classes per band for status badges (background + text + border).
 * Tuned for the dark-mode shell.
 */
export const BAND_BADGE_CLASSES: Record<RiskBand, string> = {
  low: "bg-green-500/15 text-green-400 border border-green-500/30",
  elevated: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  high: "bg-red-500/15 text-red-400 border border-red-500/30",
};

/** Return the Tailwind badge classes for a risk band. */
export function bandBadgeClasses(band: RiskBand): string {
  return BAND_BADGE_CLASSES[band];
}

/** Human-friendly label for a band (capitalized). */
export function bandLabel(band: RiskBand): string {
  return band.charAt(0).toUpperCase() + band.slice(1);
}

// ---- Numeric / date formatting utilities ----

/**
 * Format a latency in milliseconds. Sub-second values stay in `ms`; larger
 * values switch to seconds with two decimals (e.g. `1.25 s`).
 */
export function formatLatencyMs(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

/**
 * Format a value that is already expressed in percent units (e.g. a
 * `refinery_run_rate_pct` of 87.5 -> "87.5%").
 */
export function formatPercent(value: number, fractionDigits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return `${value.toFixed(fractionDigits)}%`;
}

/**
 * Format a 0..1 fraction as a percentage (e.g. a `tanker_availability` of
 * 0.82 -> "82%"). Useful for the [0,1] attributes on procurement options.
 */
export function formatFraction(value: number, fractionDigits = 0): string {
  if (!Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

const USD_FORMATTER = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Format a USD amount (e.g. spot price per barrel) -> "$82.40". */
export function formatUsd(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return USD_FORMATTER.format(value);
}

const DATETIME_FORMATTER = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * Format an ISO 8601 timestamp for display in signal lists and the timeline.
 * Returns the raw input if it cannot be parsed.
 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return DATETIME_FORMATTER.format(date);
}

/** Round a 0..100 risk score to a whole number for compact display. */
export function formatScore(score: number): string {
  if (!Number.isFinite(score)) return "—";
  return String(Math.round(score));
}
