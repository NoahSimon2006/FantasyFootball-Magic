// @vitest-environment node
// (The data module runs on the server, so these tests use Node's fetch types, not a DOM.)
import { cacheLife } from "next/cache";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  makeApiError,
  makeValuesResponse,
} from "@/components/rankings/fixtures";
import { createApiClient } from "@/lib/api/client";

import { fetchRankings, getRankings } from "./data";
import type { RankingsQuery } from "./query";

// Outside Next.js there is no cache to configure; record the calls instead.
vi.mock("next/cache", () => ({ cacheLife: vi.fn() }));

const QUERY: RankingsQuery = {
  format: { teams: 10, ppr: 0.5, superflex: true },
  position: "WR",
  offset: 50,
};

/** Stands in for fetch: records every request and answers each with `body` as JSON. */
function fakeFetch(body: unknown, status = 200) {
  const requests: Request[] = [];
  const fetch = vi.fn(async (request: Request) => {
    requests.push(request);
    return Response.json(body, { status });
  });
  return { fetch, requests };
}

function unreachableFetch() {
  return vi.fn(async () => {
    throw new TypeError("fetch failed");
  });
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("fetchRankings", () => {
  it("asks the values endpoint for one page in the requested format", async () => {
    const { fetch, requests } = fakeFetch(makeValuesResponse());
    const client = createApiClient({ baseUrl: "http://api.test", fetch });

    await fetchRankings(client, QUERY);

    const url = new URL(requests[0]?.url ?? "");
    expect([url.pathname, Object.fromEntries(url.searchParams)]).toEqual([
      "/api/v1/values",
      {
        teams: "10",
        ppr: "0.5",
        superflex: "true",
        position: "WR",
        limit: "50",
        offset: "50",
      },
    ]);
  });

  it("leaves the position out when showing every position", async () => {
    const { fetch, requests } = fakeFetch(makeValuesResponse());
    const client = createApiClient({ baseUrl: "http://api.test", fetch });

    await fetchRankings(client, { ...QUERY, position: undefined });

    expect(new URL(requests[0]?.url ?? "").searchParams.has("position")).toBe(
      false,
    );
  });

  it("returns the page of players the API sent", async () => {
    const data = makeValuesResponse();
    const { fetch } = fakeFetch(data);
    const client = createApiClient({ baseUrl: "http://api.test", fetch });

    await expect(fetchRankings(client, QUERY)).resolves.toEqual({
      kind: "ok",
      data,
    });
  });

  it("reports 'nothing loaded yet' when the API has no projections", async () => {
    const { fetch } = fakeFetch(makeApiError("VALUES_UNAVAILABLE"), 503);
    const client = createApiClient({ baseUrl: "http://api.test", fetch });

    await expect(fetchRankings(client, QUERY)).resolves.toEqual({
      kind: "unavailable",
    });
  });

  it("reports an error when the API can't be reached", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: unreachableFetch(),
    });

    await expect(fetchRankings(client, QUERY)).resolves.toEqual({
      kind: "error",
    });
  });
});

// getRankings uses the app's real client, which looks up the global fetch on every request.
describe("getRankings", () => {
  it("keeps a good page of rankings for five minutes", async () => {
    vi.stubGlobal("fetch", fakeFetch(makeValuesResponse()).fetch);

    await getRankings(QUERY);

    expect(cacheLife).toHaveBeenCalledWith({
      stale: 300,
      revalidate: 300,
      expire: 3600,
    });
  });

  it("re-checks 'nothing loaded yet' within seconds", async () => {
    vi.stubGlobal(
      "fetch",
      fakeFetch(makeApiError("VALUES_UNAVAILABLE"), 503).fetch,
    );

    await getRankings(QUERY);

    expect(cacheLife).toHaveBeenCalledWith("seconds");
  });

  it("shows the error state for a failed read and gives it no cache lifetime", async () => {
    vi.stubGlobal("fetch", unreachableFetch());

    const result = await getRankings(QUERY);

    expect([result, vi.mocked(cacheLife).mock.calls]).toEqual([
      { kind: "error" },
      [],
    ]);
  });
});
