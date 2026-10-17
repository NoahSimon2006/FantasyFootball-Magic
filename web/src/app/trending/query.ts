import type { SearchParams } from "@/components/rankings/href";
import {
  DEFAULT_WINDOW,
  TRENDING_WINDOWS,
  type TrendingWindow,
} from "@/components/trending/types";
import {
  parseFormatParams,
  type LeagueFormatParams,
} from "@/lib/league-format";

/** Everything in the URL that decides what /trending shows. */
export interface TrendingQuery {
  format: LeagueFormatParams;
  days: TrendingWindow;
}

/** "14" picks the two-week window; anything else is the default week. */
export function parseWindow(
  raw: string | string[] | undefined,
): TrendingWindow {
  const value = (Array.isArray(raw) ? raw[0] : raw)?.trim();
  return (
    TRENDING_WINDOWS.find((days) => String(days) === value) ?? DEFAULT_WINDOW
  );
}

/** Reads the URL tolerantly: a missing or invalid param falls back to its default. */
export function parseTrendingQuery(search: SearchParams): TrendingQuery {
  return { format: parseFormatParams(search), days: parseWindow(search.days) };
}
