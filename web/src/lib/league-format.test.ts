import { describe, expect, it } from "vitest";

import {
  DEFAULT_FORMAT,
  describeFormat,
  formatToQuery,
  parseFormatParams,
  type LeagueFormatParams,
} from "./league-format";

describe("parseFormatParams", () => {
  it("uses 12-team, full PPR, 1QB when the URL has no format", () => {
    expect(parseFormatParams({})).toEqual({
      teams: 12,
      ppr: 1,
      superflex: false,
    });
  });

  it("reads a valid team count, scoring and superflex setting", () => {
    expect(
      parseFormatParams({ teams: "10", ppr: "0.5", superflex: "true" }),
    ).toEqual({ teams: 10, ppr: 0.5, superflex: true });
  });

  it.each([
    { teams: "11" }, // a valid league size, but not one the picker offers
    { teams: "abc" },
    { teams: "" },
    { teams: "0x10" },
    { ppr: "2" },
    { ppr: "" },
    { ppr: "half" },
    { superflex: "maybe" },
  ])("falls back to the default for invalid input %o", (search) => {
    expect(parseFormatParams(search)).toEqual(DEFAULT_FORMAT);
  });

  it("keeps the valid fields when another field is invalid", () => {
    expect(
      parseFormatParams({ teams: "99", ppr: "0", superflex: "1" }),
    ).toEqual({ teams: 12, ppr: 0, superflex: true });
  });

  it("uses the first value when a param is repeated", () => {
    expect(
      parseFormatParams({ teams: ["14", "8"], superflex: ["false", "true"] }),
    ).toEqual({ teams: 14, ppr: 1, superflex: false });
  });

  it.each<LeagueFormatParams>([
    { teams: 8, ppr: 0, superflex: true },
    { teams: 14, ppr: 0.5, superflex: false },
    { teams: 16, ppr: 1, superflex: true },
  ])("reads back %o after it is written to a URL", (format) => {
    // The same stringify-then-parse trip the FormatPicker and the page make.
    const url = new URLSearchParams(
      Object.entries(formatToQuery(format)).map(([key, value]) => [
        key,
        String(value),
      ]),
    );

    expect(parseFormatParams(Object.fromEntries(url))).toEqual(format);
  });
});

describe("describeFormat", () => {
  it.each([
    [{ teams: 12, ppr: 1, superflex: false }, "12-team · Full PPR · 1QB"],
    [
      { teams: 10, ppr: 0.5, superflex: true },
      "10-team · Half PPR · Superflex",
    ],
    [{ teams: 8, ppr: 0, superflex: false }, "8-team · Standard · 1QB"],
  ])("describes %o as %s", (format, text) => {
    expect(describeFormat(format)).toBe(text);
  });
});

describe("formatToQuery", () => {
  it("maps a format onto the API's teams, ppr and superflex fields", () => {
    expect(formatToQuery({ teams: 14, ppr: 0.5, superflex: true })).toEqual({
      teams: 14,
      ppr: 0.5,
      superflex: true,
    });
  });
});
