import { describe, expect, it } from "vitest";

import { hrefWith } from "./href";

describe("hrefWith", () => {
  it("keeps the other params and sets the changed one", () => {
    expect(
      hrefWith("/rankings", { teams: "10", ppr: "0.5" }, { position: "WR" }),
    ).toBe("/rankings?teams=10&ppr=0.5&position=WR");
  });

  it("replaces a param that is already there", () => {
    expect(
      hrefWith(
        "/rankings",
        { position: "QB", teams: "10" },
        { position: "TE" },
      ),
    ).toBe("/rankings?teams=10&position=TE");
  });

  it("removes a param whose change is null", () => {
    expect(
      hrefWith("/rankings", { offset: "50", teams: "10" }, { offset: null }),
    ).toBe("/rankings?teams=10");
  });

  it("keeps every value of a repeated param", () => {
    expect(hrefWith("/trending", { tag: ["a", "b"] }, {})).toBe(
      "/trending?tag=a&tag=b",
    );
  });

  it("returns the bare path when no params are left", () => {
    expect(hrefWith("/rankings", { position: "WR" }, { position: null })).toBe(
      "/rankings",
    );
  });
});
