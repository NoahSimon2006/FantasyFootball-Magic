import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("Home page", () => {
  it("leads with the value proposition as the page's only h1", () => {
    render(<HomePage />);

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Who wins this trade, and by how much?",
      }),
    ).toBeInTheDocument();
  });

  it.each([
    ["Trade calculator", "/calculator"],
    ["Rankings", "/rankings"],
    ["Trending", "/trending"],
  ])("has a feature card linking %s to %s", (name, href) => {
    render(<HomePage />);

    expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
  });

  it("says plainly that v0 values come from projections, not trades yet", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { level: 2, name: /how the values work/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/v0 uses projections only/i)).toBeInTheDocument();
  });
});
