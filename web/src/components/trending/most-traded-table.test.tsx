import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makePlayerRef, makeTradedPlayer } from "./fixtures";
import { MostTradedTable } from "./most-traded-table";

describe("MostTradedTable", () => {
  it("shows this window's trades next to the window before, with the change", () => {
    render(
      <MostTradedTable
        days={7}
        players={[
          makeTradedPlayer({ trades: 12, previous_trades: 8, change: 4 }),
        ]}
      />,
    );

    const row = screen.getByRole("row", { name: /Patrick Mahomes/ });
    expect(
      within(row)
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual(["12", "8", "▲+4"]);
  });

  it("names the window in the column headers", () => {
    render(<MostTradedTable days={14} players={[makeTradedPlayer()]} />);

    expect(
      screen.getAllByRole("columnheader").map((header) => header.textContent),
    ).toEqual(["Player", "Last 14 days", "14 days before", "Change"]);
  });

  it("marks a player traded less than before with a down arrow", () => {
    render(
      <MostTradedTable
        days={7}
        players={[
          makeTradedPlayer({
            player: makePlayerRef({ player_id: "1", name: "Derrick Henry" }),
            trades: 2,
            previous_trades: 5,
            change: -3,
          }),
        ]}
      />,
    );

    expect(screen.getByText("−3").textContent).toBe("▼−3");
  });
});
