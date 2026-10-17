import { describe, expect, it } from "vitest";

import { DEFAULT_FORMAT } from "@/lib/league-format";

import {
  PAGE_SIZE,
  parseOffset,
  parsePosition,
  parseRankingsQuery,
} from "./query";

describe("parseRankingsQuery", () => {
  it("defaults to every position, the first page, and the default format", () => {
    expect(parseRankingsQuery({})).toEqual({
      format: DEFAULT_FORMAT,
      position: undefined,
      offset: 0,
    });
  });

  it("reads the format, position, and offset from the URL", () => {
    expect(
      parseRankingsQuery({
        teams: "10",
        ppr: "0.5",
        superflex: "true",
        position: "RB",
        offset: "100",
      }),
    ).toEqual({
      format: { teams: 10, ppr: 0.5, superflex: true },
      position: "RB",
      offset: 100,
    });
  });
});

describe("parsePosition", () => {
  it("accepts a position in any case", () => {
    expect(parsePosition("wr")).toBe("WR");
  });

  it.each([["K"], ["ALL"], [""], [undefined]])(
    "treats %j as all positions",
    (raw) => {
      expect(parsePosition(raw)).toBeUndefined();
    },
  );

  it("uses the first of repeated values", () => {
    expect(parsePosition(["TE", "QB"])).toBe("TE");
  });
});

describe("parseOffset", () => {
  it("keeps an offset that starts a page", () => {
    expect(parseOffset(String(PAGE_SIZE * 2))).toBe(PAGE_SIZE * 2);
  });

  it("rounds an offset down to the start of its page", () => {
    expect(parseOffset("73")).toBe(50);
  });

  it.each([["-50"], ["1e3"], ["abc"], [""], ["99999999999999999999"]])(
    "treats %j as the first page",
    (raw) => {
      expect(parseOffset(raw)).toBe(0);
    },
  );
});
