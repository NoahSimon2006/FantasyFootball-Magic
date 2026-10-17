import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WindowSelector } from "./window-selector";

describe("WindowSelector", () => {
  it("keeps the league format in the window links", () => {
    render(<WindowSelector current={7} search={{ teams: "10", ppr: "0" }} />);

    expect(screen.getByRole("link", { name: "14 days" })).toHaveAttribute(
      "href",
      "/trending?teams=10&ppr=0&days=14",
    );
  });

  it("links the default week without a days param", () => {
    render(<WindowSelector current={14} search={{ days: "14", teams: "8" }} />);

    expect(screen.getByRole("link", { name: "7 days" })).toHaveAttribute(
      "href",
      "/trending?teams=8",
    );
  });

  it("marks only the current window with aria-current", () => {
    render(<WindowSelector current={14} search={{}} />);

    expect(
      screen
        .getAllByRole("link")
        .map((link) => [link.textContent, link.getAttribute("aria-current")]),
    ).toEqual([
      ["7 days", null],
      ["14 days", "true"],
    ]);
  });
});
