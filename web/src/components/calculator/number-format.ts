// Fixed "en-US" so server and browser (and tests) always print the same text.
const POINTS = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const PERCENT = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const DATE = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeZone: "UTC",
});

/** Fantasy points or value points, to one decimal: 14.2. */
export function formatPoints(points: number): string {
  return POINTS.format(points);
}

/** A 0-1 share as a percent, to one decimal: 0.114 -> "11.4%". */
export function formatPercent(share: number): string {
  return PERCENT.format(share);
}

/**
 * "2026-10-14" -> "Oct 14, 2026". Read as UTC: parsed in local time, a bare date shows as
 * the previous day anywhere west of Greenwich.
 */
export function formatSnapshotDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? isoDate : DATE.format(date);
}
