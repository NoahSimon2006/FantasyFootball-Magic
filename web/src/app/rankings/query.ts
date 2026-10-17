import type { SearchParams } from "@/components/rankings/href";
import { POSITIONS, type Position } from "@/components/rankings/types";
import {
  parseFormatParams,
  type LeagueFormatParams,
} from "@/lib/league-format";

/** Players per page. */
export const PAGE_SIZE = 50;

/** Everything in the URL that decides which rankings to show. */
export interface RankingsQuery {
  format: LeagueFormatParams;
  /** `undefined` means all positions. */
  position: Position | undefined;
  /** Index of the first player on the page; always a multiple of PAGE_SIZE. */
  offset: number;
}

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** "WR" or "wr"; anything else means all positions. */
export function parsePosition(
  raw: string | string[] | undefined,
): Position | undefined {
  const value = firstValue(raw)?.trim().toUpperCase();
  return POSITIONS.find((position) => position === value);
}

/** A whole number of players to skip, rounded down to the start of its page; else 0. */
export function parseOffset(raw: string | string[] | undefined): number {
  const value = firstValue(raw)?.trim();
  if (value === undefined || !/^\d+$/.test(value)) return 0;
  const offset = Number(value);
  if (!Number.isSafeInteger(offset)) return 0;
  return offset - (offset % PAGE_SIZE);
}

/** Reads the URL tolerantly: a missing or invalid param falls back to its default. */
export function parseRankingsQuery(search: SearchParams): RankingsQuery {
  return {
    format: parseFormatParams(search),
    position: parsePosition(search.position),
    offset: parseOffset(search.offset),
  };
}
