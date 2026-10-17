import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NavLinks } from "./site-nav";

describe("NavLinks", () => {
  it("marks only the current page's link with aria-current", () => {
    render(<NavLinks pathname="/calculator" />);

    expect(screen.getByRole("link", { name: "Calculator" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("marks a section's link on the pages inside it", () => {
    render(<NavLinks pathname="/rankings/wr" />);

    expect(screen.getByRole("link", { name: "Rankings" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("marks nothing while the pathname is unknown", () => {
    render(<NavLinks pathname={null} />);

    expect(
      screen
        .getAllByRole("link")
        .filter((link) => link.hasAttribute("aria-current")),
    ).toHaveLength(0);
  });
});
