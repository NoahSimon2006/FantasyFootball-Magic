import { describe, expect, it } from "vitest";

import {
  formatCount,
  formatDate,
  formatPoints,
  formatSignedCount,
  formatSignedPoints,
} from "./format";

describe("formatPoints", () => {
  it("shows one decimal and groups thousands", () => {
    expect([formatPoints(182.44), formatPoints(1204)]).toEqual([
      "182.4",
      "1,204.0",
    ]);
  });
});

describe("formatSignedPoints", () => {
  it("spells out the sign, using a typographic minus for drops", () => {
    expect([
      formatSignedPoints(6.24),
      formatSignedPoints(-3),
      formatSignedPoints(0),
    ]).toEqual(["+6.2", "−3.0", "0.0"]);
  });
});

describe("formatSignedCount", () => {
  it("spells out the sign of a whole-number change", () => {
    expect([
      formatSignedCount(4),
      formatSignedCount(-2),
      formatSignedCount(0),
    ]).toEqual(["+4", "−2", "0"]);
  });
});

describe("formatCount", () => {
  it("groups thousands", () => {
    expect(formatCount(1024)).toBe("1,024");
  });
});

describe("formatDate", () => {
  it("shows the calendar day the API sent, whatever the local time zone", () => {
    expect(formatDate("2026-10-14")).toBe("Oct 14, 2026");
  });

  it("shows an unparseable date as given rather than 'Invalid Date'", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });
});
