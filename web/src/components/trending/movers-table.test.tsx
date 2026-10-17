import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makeValueMove } from "./fixtures";
import { MoversTable } from "./movers-table";

describe("MoversTable", () => {
  it("shows a riser's value now and before, the signed change, and projected points", () => {
    render(
      <MoversTable
        caption="Risers"
        moves={[
          makeValueMove({
            value_now: 41.2,
            value_then: 35,
            change: 6.2,
            ros_points_now: 182.4,
          }),
        ]}
      />,
    );

    const row = screen.getByRole("row", { name: /Bijan Robinson/ });
    expect(
      within(row)
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual(["41.2was 35.0", "▲+6.2", "182.4"]);
  });

  it("shows a faller's change with a down arrow and a minus sign", () => {
    render(
      <MoversTable
        caption="Fallers"
        moves={[
          makeValueMove({ value_now: 52, value_then: 60.5, change: -8.5 }),
        ]}
      />,
    );

    expect(screen.getByText("−8.5").textContent).toBe("▼−8.5");
  });

  it("is a table named by its caption", () => {
    render(<MoversTable caption="Fallers" moves={[makeValueMove()]} />);

    expect(screen.getByRole("table", { name: "Fallers" })).toBeInTheDocument();
  });
});
