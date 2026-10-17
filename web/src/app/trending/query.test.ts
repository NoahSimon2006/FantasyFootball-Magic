import { describe, expect, it } from "vitest";

import { DEFAULT_FORMAT } from "@/lib/league-format";

import { parseTrendingQuery, parseWindow } from "./query";

describe("parseTrendingQuery", () => {
  it("defaults to a one-week window in the default format", () => {
    expect(parseTrendingQuery({})).toEqual({ format: DEFAULT_FORMAT, days: 7 });
  });

  it("reads the format and window from the URL", () => {
    expect(parseTrendingQuery({ teams: "14", ppr: "0", days: "14" })).toEqual({
      format: { teams: 14, ppr: 0, superflex: false },
      days: 14,
    });
  });
});

describe("parseWindow", () => {
  it.each([["30"], ["0"], ["two weeks"], [""], [undefined]])(
    "falls back to 7 days for %j",
    (raw) => {
      expect(parseWindow(raw)).toBe(7);
    },
  );

  it("uses the first of repeated values", () => {
    expect(parseWindow(["14", "7"])).toBe(14);
  });
});
