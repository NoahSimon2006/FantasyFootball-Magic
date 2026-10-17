import { cacheLife } from "next/cache";

import type { Outcome, ValuesResponse } from "@/components/rankings/types";
import { api, type ApiClient } from "@/lib/api/client";
import { formatToQuery } from "@/lib/league-format";

import { PAGE_SIZE, type RankingsQuery } from "./query";
import { API_TIMEOUT_MS, readApi } from "./read-api";

export type RankingsResult = Outcome<ValuesResponse>;

/** One page of rankings from GET /api/v1/values. Never throws; tests pass a fake client. */
export function fetchRankings(
  client: ApiClient,
  query: RankingsQuery,
): Promise<RankingsResult> {
  return readApi("GET /api/v1/values", () =>
    client.GET("/api/v1/values", {
      params: {
        query: {
          ...formatToQuery(query.format),
          position: query.position,
          limit: PAGE_SIZE,
          offset: query.offset,
        },
      },
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    }),
  );
}

// Why this is cached, and how it fits Cache Components (`cacheComponents: true`):
//
// Values change at most once a day (one projection snapshot per day), so reusing a page of
// rankings for a few minutes costs nothing in accuracy and saves the API from re-valuing
// every player on each page view, filter click, and page turn.
//
// - The page reads `searchParams` inside <Suspense>, so this runs at request time only. The
//   build never calls it, which is why `next build` works with the API down.
// - The cache key is the argument: the parsed query (format, position, offset), not the raw
//   URL, so `?ppr=1` and `?ppr=1.0` share an entry.
// - Only answers worth reusing are stored. A real page is kept for 5 minutes. "No projections
//   yet" is kept for seconds, because it flips to real data the moment the first load ends.
//   A failure is thrown: Next.js stores nothing for a cached function that throws, so the
//   next request asks the API again instead of replaying the outage.
async function loadRankings(query: RankingsQuery): Promise<RankingsResult> {
  "use cache";
  const result = await fetchRankings(api, query);
  if (result.kind === "error") {
    throw new Error("GET /api/v1/values failed (not cached)");
  }
  if (result.kind === "ok") {
    cacheLife({ stale: 300, revalidate: 300, expire: 3600 });
  } else {
    cacheLife("seconds");
  }
  return result;
}

/** The page's single entry point: always resolves to one of the three outcomes. */
export async function getRankings(
  query: RankingsQuery,
): Promise<RankingsResult> {
  try {
    return await loadRankings(query);
  } catch {
    // readApi has already logged the cause; the page shows its error state.
    return { kind: "error" };
  }
}
