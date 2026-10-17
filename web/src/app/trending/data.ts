import { cacheLife } from "next/cache";

import { API_TIMEOUT_MS, readApi } from "@/app/rankings/read-api";
import type { Outcome } from "@/components/rankings/types";
import type {
  MoversHistory,
  TrendingData,
  TrendingResponse,
} from "@/components/trending/types";
import { api, type ApiClient } from "@/lib/api/client";
import { formatToQuery } from "@/lib/league-format";

import type { TrendingQuery } from "./query";

/** Players per list. */
export const TRENDING_LIMIT = 10;

export type TrendingResult = Outcome<TrendingData>;

/**
 * GET /api/v1/trending, plus (only when needed) one small values read to explain empty
 * risers and fallers. Never throws; tests pass a fake client.
 */
export async function fetchTrending(
  client: ApiClient,
  query: TrendingQuery,
): Promise<TrendingResult> {
  const outcome = await readApi("GET /api/v1/trending", () =>
    client.GET("/api/v1/trending", {
      params: {
        query: {
          ...formatToQuery(query.format),
          days: query.days,
          limit: TRENDING_LIMIT,
        },
      },
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    }),
  );
  if (outcome.kind !== "ok") return outcome;
  return {
    kind: "ok",
    data: {
      trending: outcome.data,
      history: await moversHistory(client, query, outcome.data),
    },
  };
}

async function moversHistory(
  client: ApiClient,
  query: TrendingQuery,
  trending: TrendingResponse,
): Promise<MoversHistory> {
  const { snapshot_date: snapshotDate, compared_to: comparedTo } = trending;
  if (snapshotDate !== null && comparedTo !== null) {
    return { kind: "ready", snapshotDate, comparedTo };
  }
  if (snapshotDate !== null) {
    return { kind: "building", latestSnapshot: snapshotDate };
  }
  // The trending endpoint answers 200 with empty lists and no dates both when no projections
  // exist and when history is too short. The values endpoint tells the two apart: it answers
  // 503 VALUES_UNAVAILABLE only when nothing has been loaded.
  const probe = await readApi("GET /api/v1/values (history probe)", () =>
    client.GET("/api/v1/values", {
      params: { query: { ...formatToQuery(query.format), limit: 1 } },
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    }),
  );
  switch (probe.kind) {
    case "ok":
      return { kind: "building", latestSnapshot: probe.data.snapshot_date };
    case "unavailable":
      return { kind: "no-projections" };
    case "error":
      // Can't tell; the generic "history is building" message is still true either way.
      return { kind: "building", latestSnapshot: null };
  }
}

// Cached for the same reasons, and in the same way, as rankings (see app/rankings/data.ts):
// it runs at request time behind <Suspense>, keys on the parsed query, keeps a good answer
// for 5 minutes, re-checks "nothing loaded yet" within seconds, and never stores a failure.
async function loadTrending(query: TrendingQuery): Promise<TrendingResult> {
  "use cache";
  const result = await fetchTrending(api, query);
  if (result.kind === "error") {
    throw new Error("GET /api/v1/trending failed (not cached)");
  }
  if (result.kind === "ok" && result.data.history.kind !== "no-projections") {
    cacheLife({ stale: 300, revalidate: 300, expire: 3600 });
  } else {
    cacheLife("seconds");
  }
  return result;
}

/** The page's single entry point: always resolves to one of the three outcomes. */
export async function getTrending(
  query: TrendingQuery,
): Promise<TrendingResult> {
  try {
    return await loadTrending(query);
  } catch {
    // readApi has already logged the cause; the page shows its error state.
    return { kind: "error" };
  }
}
