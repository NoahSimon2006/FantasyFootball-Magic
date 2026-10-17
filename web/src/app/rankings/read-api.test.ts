// @vitest-environment node
// (Server-side code: these tests use Node's Response, not a fake DOM.)
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  makeApiError,
  makeValuesResponse,
} from "@/components/rankings/fixtures";

import { apiErrorCode, readApi } from "./read-api";

/** What openapi-fetch hands back for a response with this status and parsed body. */
function apiResult(status: number, body: unknown) {
  const response = new Response(null, { status });
  return response.ok
    ? { data: body, response }
    : { data: undefined, error: body, response };
}

describe("apiErrorCode", () => {
  it("reads the code from the API's error shape", () => {
    expect(apiErrorCode(makeApiError("VALUES_UNAVAILABLE"))).toBe(
      "VALUES_UNAVAILABLE",
    );
  });

  it.each([
    ["a FastAPI-style detail body", { detail: "Not Found" }],
    ["a non-string code", { error: { code: 503 } }],
    ["plain text", "Bad Gateway"],
    ["no body", undefined],
  ])("returns undefined for %s", (_label, body) => {
    expect(apiErrorCode(body)).toBeUndefined();
  });
});

describe("readApi", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the data of a successful response", async () => {
    const data = makeValuesResponse();

    await expect(
      readApi("test", async () => apiResult(200, data)),
    ).resolves.toEqual({ kind: "ok", data });
  });

  it("reports 503 VALUES_UNAVAILABLE as 'nothing loaded yet', not as an error", async () => {
    const result = await readApi("test", async () =>
      apiResult(503, makeApiError("VALUES_UNAVAILABLE")),
    );

    expect(result).toEqual({ kind: "unavailable" });
  });

  it("treats any other 503 as an error", async () => {
    const result = await readApi("test", async () =>
      apiResult(503, makeApiError("MAINTENANCE")),
    );

    expect(result).toEqual({ kind: "error" });
  });

  it("treats a validation error as an error", async () => {
    const result = await readApi("test", async () =>
      apiResult(422, makeApiError("VALIDATION_ERROR")),
    );

    expect(result).toEqual({ kind: "error" });
  });

  it("turns an unreachable API into an error instead of throwing", async () => {
    const result = await readApi("test", async () => {
      throw new TypeError("fetch failed");
    });

    expect(result).toEqual({ kind: "error" });
  });

  it("logs why a read failed, with its label", async () => {
    await readApi("GET /api/v1/values", async () =>
      apiResult(500, makeApiError("INTERNAL")),
    );

    expect(console.error).toHaveBeenCalledWith(
      "GET /api/v1/values: the API answered 500 INTERNAL",
    );
  });
});
