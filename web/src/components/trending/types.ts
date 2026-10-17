// Names for the generated API types /trending uses (aliases, not copies; see schema.d.ts),
// plus the page's own view of whether risers and fallers can be shown yet.
import type { components } from "@/lib/api/schema";

export type TrendingResponse = components["schemas"]["TrendingResponse"];
export type TradedPlayer = components["schemas"]["TradedPlayerOut"];
export type ValueMove = components["schemas"]["ValueMoveOut"];

/** The windows the page offers, in days (the API accepts 1–30). */
export const TRENDING_WINDOWS = [7, 14] as const;
export type TrendingWindow = (typeof TRENDING_WINDOWS)[number];
export const DEFAULT_WINDOW: TrendingWindow = 7;

/**
 * Risers and fallers compare two projection snapshots at least `days` apart, so they can't
 * exist during the first days of data. This says which situation the page is in.
 */
export type MoversHistory =
  /** Both snapshots exist; the lists compare `snapshotDate` with `comparedTo`. */
  | { kind: "ready"; snapshotDate: string; comparedTo: string }
  /** Projections exist (the newest from `latestSnapshot`, if known) but not enough history. */
  | { kind: "building"; latestSnapshot: string | null }
  /** No projections have been loaded at all yet. */
  | { kind: "no-projections" };

export interface TrendingData {
  trending: TrendingResponse;
  history: MoversHistory;
}
