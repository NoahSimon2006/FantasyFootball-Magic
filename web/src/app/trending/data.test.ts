// @vitest-environment node
// (The data module runs on the server, so these tests use Node's fetch types, not a DOM.)
import { cacheLife } from "next/cache";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  makeApiError,
  makeValuesResponse,
} from "@/components/rankings/fixtures";
import { makeTrendingResponse } from "@/components/trending/fixtures";
import { createApiClient } from "@/lib/api/client";

import { fetchTrending, getTrending } from "./data";
import type { TrendingQuery } from "./query";

// Outside Next.js there is no cache to configure; record the calls instead.
vi.mock("next/cache", () => ({ cacheLife: vi.fn() }));

const QUERY: TrendingQuery = {
  format: { teams: 10, ppr: 0.5, superflex: true },
  days: 14,
};

type Route = { status?: number; body: unknown } | Error;

/** A fake API: answers by request path, records every request, rejects unknown paths. */
function fakeApi(routes: Record<string, Route>) {
  const requests: Request[] = [];
  const fetch = vi.fn(async (request: Request) => {
    requests.push(request);
    const route = routes[new URL(request.url).pathname];
    if (route === undefined) throw new Error(`unexpected ${request.url}`);
    if (route instanceof Error) throw route;
    return Response.json(route.body, { status: route.status ?? 200 });
  });
  return {
    client: createApiClient({ baseUrl: "http://api.test", fetch }),
    fetch,
    requests,
  };
}

/** The trending answer while history is too short: no dates, no movers. */
const SHORT_HISTORY = makeTrendingResponse({
  snapshot_date: null,
  compared_to: null,
  risers: [],
  fallers: [],
});

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("fetchTrending", () => {
  it("asks for the requested window and format, ten players per list", async () => {
    const { client, requests } = fakeApi({
      "/api/v1/trending": { body: makeTrendingResponse() },
    });

    await fetchTrending(client, QUERY);

    expect(
      Object.fromEntries(new URL(requests[0]?.url ?? "").searchParams),
    ).toEqual({
      teams: "10",
      ppr: "0.5",
      superflex: "true",
      days: "14",
      limit: "10",
    });
  });

  it("marks risers and fallers ready when both snapshot dates are present", async () => {
    const { client, requests } = fakeApi({
      "/api/v1/trending": { body: makeTrendingResponse() },
    });

    const result = await fetchTrending(client, QUERY);

    expect([
      result.kind === "ok" ? result.data.history : result,
      requests.length,
    ]).toEqual([
      { kind: "ready", snapshotDate: "2026-10-14", comparedTo: "2026-10-07" },
      1,
    ]);
  });

  it("reports building history, with the latest snapshot, when the API sends one", async () => {
    const { client } = fakeApi({
      "/api/v1/trending": {
        body: makeTrendingResponse({
          compared_to: null,
          risers: [],
          fallers: [],
        }),
      },
    });

    const result = await fetchTrending(client, QUERY);

    expect(result.kind === "ok" && result.data.history).toEqual({
      kind: "building",
      latestSnapshot: "2026-10-14",
    });
  });

  it("asks the values endpoint whether projections exist when trending can't say", async () => {
    const { client, requests } = fakeApi({
      "/api/v1/trending": { body: SHORT_HISTORY },
      "/api/v1/values": {
        body: makeValuesResponse({ snapshot_date: "2026-10-15" }),
      },
    });

    const result = await fetchTrending(client, QUERY);

    expect([
      result.kind === "ok" && result.data.history,
      requests.map((request) => new URL(request.url).pathname),
    ]).toEqual([
      { kind: "building", latestSnapshot: "2026-10-15" },
      ["/api/v1/trending", "/api/v1/values"],
    ]);
  });

  it("reports that no projections are loaded when the values endpoint says so", async () => {
    const { client } = fakeApi({
      "/api/v1/trending": { body: SHORT_HISTORY },
      "/api/v1/values": {
        status: 503,
        body: makeApiError("VALUES_UNAVAILABLE"),
      },
    });

    const result = await fetchTrending(client, QUERY);

    expect(result.kind === "ok" && result.data.history).toEqual({
      kind: "no-projections",
    });
  });

  it("falls back to the general 'building history' message when the probe fails", async () => {
    const { client } = fakeApi({
      "/api/v1/trending": { body: SHORT_HISTORY },
      "/api/v1/values": new TypeError("fetch failed"),
    });

    const result = await fetchTrending(client, QUERY);

    expect(result.kind === "ok" && result.data.history).toEqual({
      kind: "building",
      latestSnapshot: null,
    });
  });

  it("keeps the most-traded list while history is building", async () => {
    const { client } = fakeApi({
      "/api/v1/trending": { body: SHORT_HISTORY },
      "/api/v1/values": { body: makeValuesResponse() },
    });

    const result = await fetchTrending(client, QUERY);

    expect(result.kind === "ok" && result.data.trending.most_traded).toEqual(
      SHORT_HISTORY.most_traded,
    );
  });

  it("reports 'nothing loaded yet' if trending answers 503 VALUES_UNAVAILABLE", async () => {
    const { client } = fakeApi({
      "/api/v1/trending": {
        status: 503,
        body: makeApiError("VALUES_UNAVAILABLE"),
      },
    });

    await expect(fetchTrending(client, QUERY)).resolves.toEqual({
      kind: "unavailable",
    });
  });

  it("reports an error when the API can't be reached", async () => {
    const { client } = fakeApi({
      "/api/v1/trending": new TypeError("fetch failed"),
    });

    await expect(fetchTrending(client, QUERY)).resolves.toEqual({
      kind: "error",
    });
  });
});

// getTrending uses the app's real client, which looks up the global fetch on every request.
describe("getTrending", () => {
  it("keeps a good answer for five minutes", async () => {
    vi.stubGlobal(
      "fetch",
      fakeApi({ "/api/v1/trending": { body: makeTrendingResponse() } }).fetch,
    );

    await getTrending(QUERY);

    expect(cacheLife).toHaveBeenCalledWith({
      stale: 300,
      revalidate: 300,
      expire: 3600,
    });
  });

  it("re-checks within seconds while no projections are loaded", async () => {
    vi.stubGlobal(
      "fetch",
      fakeApi({
        "/api/v1/trending": { body: SHORT_HISTORY },
        "/api/v1/values": {
          status: 503,
          body: makeApiError("VALUES_UNAVAILABLE"),
        },
      }).fetch,
    );

    await getTrending(QUERY);

    expect(cacheLife).toHaveBeenCalledWith("seconds");
  });

  it("shows the error state for a failed read and gives it no cache lifetime", async () => {
    vi.stubGlobal(
      "fetch",
      fakeApi({ "/api/v1/trending": new TypeError("fetch failed") }).fetch,
    );

    const result = await getTrending(QUERY);

    expect([result, vi.mocked(cacheLife).mock.calls]).toEqual([
      { kind: "error" },
      [],
    ]);
  });
});
