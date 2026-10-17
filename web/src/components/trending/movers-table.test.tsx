import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makeValueMove } from "./fixtures";
import { MoversTable } from "./movers-table";

describe("MoversTable", () => {
  it("shows a riser's projected points now and before, the signed points change, and value", () => {
    render(
      <MoversTable
        caption="Risers"
        moves={[
          makeValueMove({
            ros_points_now: 182.4,
            ros_points_then: 171,
            points_change: 11.4,
            value_now: 41.2,
            value_then: 35,
            change: 6.2,
          }),
        ]}
      />,
    );

    const row = screen.getByRole("row", { name: /Bijan Robinson/ });
    expect(
      within(row)
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual(["182.4was 171.0", "▲+11.4", "41.2was 35.0"]);
  });

  it("shows a faller's change with a down arrow and a minus sign", () => {
    render(
      <MoversTable
        caption="Fallers"
        moves={[makeValueMove({ points_change: -10.8 })]}
      />,
    );

    expect(screen.getByText("−10.8").textContent).toBe("▼−10.8");
  });

  it("headlines the player's own points change, not the value change", () => {
    // A player can lose value only because replacement level rose: his own projection is flat.
    render(
      <MoversTable
        caption="Risers"
        moves={[makeValueMove({ points_change: 3.1, change: -5.3 })]}
      />,
    );

    const row = screen.getByRole("row", { name: /Bijan Robinson/ });
    const changeCell = within(row).getAllByRole("cell")[1];
    expect(changeCell.textContent).toBe("▲+3.1");
  });

  it("is a table named by its caption", () => {
    render(<MoversTable caption="Fallers" moves={[makeValueMove()]} />);

    expect(screen.getByRole("table", { name: "Fallers" })).toBeInTheDocument();
  });
});
