// @vitest-environment node
// (The client runs on the server, so these tests use Node's fetch types, not a fake DOM.)
import { afterEach, describe, expect, expectTypeOf, it, vi } from "vitest";

import { createApiClient } from "./client";
import type { components } from "./schema";

const BASE_URL = "http://api.test";

/** Stands in for fetch: records every request and answers each with `body` as JSON. */
function fakeFetch(body: unknown, status = 200) {
  const requests: Request[] = [];
  async function fetch(request: Request): Promise<Response> {
    requests.push(request);
    return Response.json(body, { status });
  }
  return { fetch, requests };
}

describe("createApiClient", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("sends a GET for a schema path to <baseUrl><path>", async () => {
    const { fetch, requests } = fakeFetch({ status: "ok" });
    const api = createApiClient({ baseUrl: BASE_URL, fetch });

    await api.GET("/api/v1/health");

    expect(requests.map((r) => `${r.method} ${r.url}`)).toEqual([
      `GET ${BASE_URL}/api/v1/health`,
    ]);
  });

  it("returns the JSON body as data, typed from the generated schema", async () => {
    const { fetch } = fakeFetch({ status: "ok" });
    const api = createApiClient({ baseUrl: BASE_URL, fetch });

    const { data } = await api.GET("/api/v1/health");

    expect(data).toEqual({ status: "ok" });
    // Checked by `tsc`, not at runtime: the response type comes from schema.d.ts.
    expectTypeOf(data).toEqualTypeOf<
      components["schemas"]["HealthResponse"] | undefined
    >();
  });

  it("returns a non-2xx response as error instead of throwing", async () => {
    const body = {
      error: { code: "SLEEPER_UNAVAILABLE", message: "Sleeper API failed" },
    };
    const { fetch } = fakeFetch(body, 502);
    const api = createApiClient({ baseUrl: BASE_URL, fetch });

    const { data, error, response } = await api.GET("/api/v1/health");

    expect(response.status).toBe(502);
    expect(error).toEqual(body);
    expect(data).toBeUndefined();
  });

  it("uses the API_BASE_URL env var when no baseUrl is passed", async () => {
    vi.stubEnv("API_BASE_URL", "http://api.example:9000");
    const { fetch, requests } = fakeFetch({ status: "ok" });

    await createApiClient({ fetch }).GET("/api/v1/health");

    expect(requests[0]?.url).toBe("http://api.example:9000/api/v1/health");
  });

  it.each([
    { state: "unset", value: undefined },
    { state: "empty", value: "" },
  ])(
    "falls back to http://127.0.0.1:8000 when API_BASE_URL is $state",
    async ({ value }) => {
      vi.stubEnv("API_BASE_URL", value);
      const { fetch, requests } = fakeFetch({ status: "ok" });

      await createApiClient({ fetch }).GET("/api/v1/health");

      expect(requests[0]?.url).toBe("http://127.0.0.1:8000/api/v1/health");
    },
  );
});
