import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PositionFilter } from "./position-filter";

describe("PositionFilter", () => {
  it("keeps the league format and drops the page offset in a position link", () => {
    render(
      <PositionFilter
        current={undefined}
        search={{ teams: "10", ppr: "0.5", superflex: "true", offset: "50" }}
      />,
    );

    expect(screen.getByRole("link", { name: "WR" })).toHaveAttribute(
      "href",
      "/rankings?teams=10&ppr=0.5&superflex=true&position=WR",
    );
  });

  it("links All to the unfiltered list in the same format", () => {
    render(
      <PositionFilter current="WR" search={{ position: "WR", teams: "10" }} />,
    );

    expect(screen.getByRole("link", { name: "All" })).toHaveAttribute(
      "href",
      "/rankings?teams=10",
    );
  });

  it("marks only the current position with aria-current", () => {
    render(<PositionFilter current="RB" search={{}} />);

    expect(
      screen
        .getAllByRole("link")
        .map((link) => [link.textContent, link.getAttribute("aria-current")]),
    ).toEqual([
      ["All", null],
      ["QB", null],
      ["RB", "true"],
      ["WR", null],
      ["TE", null],
    ]);
  });

  it("is a navigation landmark named by its visible label", () => {
    render(<PositionFilter current={undefined} search={{}} />);

    expect(
      screen.getByRole("navigation", { name: "Position" }),
    ).toBeInTheDocument();
  });
});
