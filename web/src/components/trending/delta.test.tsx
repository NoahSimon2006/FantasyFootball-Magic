import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Delta } from "./delta";

describe("Delta", () => {
  it("shows a gain with an up arrow, a plus sign, and the positive colour", () => {
    render(<Delta change={6.24} unit="points" />);

    const chip = screen.getByText("+6.2");
    expect([chip.textContent, chip.className]).toEqual([
      "▲+6.2",
      expect.stringContaining("text-positive"),
    ]);
  });

  it("shows a drop with a down arrow, a minus sign, and the negative colour", () => {
    render(<Delta change={-3} unit="points" />);

    const chip = screen.getByText("−3.0");
    expect([chip.textContent, chip.className]).toEqual([
      "▼−3.0",
      expect.stringContaining("text-negative"),
    ]);
  });

  it("hides the arrow from screen readers, since the sign already says it", () => {
    render(<Delta change={2} unit="trades" />);

    expect(screen.getByText("▲")).toHaveAttribute("aria-hidden", "true");
  });

  it("counts trades in whole numbers", () => {
    render(<Delta change={4} unit="trades" />);

    expect(screen.getByText("+4")).toBeInTheDocument();
  });

  it("says 'No change' with no arrow when nothing moved", () => {
    render(<Delta change={0} unit="trades" />);

    expect(screen.getByText("No change").textContent).toBe("No change");
  });

  it("treats a change too small to show as no change", () => {
    render(<Delta change={0.04} unit="points" />);

    expect(screen.getByText("No change")).toBeInTheDocument();
  });
});
