import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("Home page", () => {
  it("shows the Fantasy Magic heading", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Fantasy Magic" }),
    ).toBeInTheDocument();
  });
});
