import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makePlayerValue } from "./fixtures";
import { RankingsTable, valueShare } from "./rankings-table";

const CAPTION = "Ranked players for 12-team · Full PPR · 1QB, 1 to 2 of 312";

describe("RankingsTable", () => {
  it("lists each player with rank, name, position and team, projected points, and value", () => {
    render(
      <RankingsTable
        caption={CAPTION}
        players={[
          makePlayerValue({
            overall_rank: 7,
            name: "Bijan Robinson",
            position: "RB",
            team: "ATL",
            ros_points: 201.35,
            value: 74.42,
          }),
        ]}
      />,
    );

    const row = screen.getByRole("row", { name: /Bijan Robinson/ });
    expect(
      within(row)
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual(["7", "201.4", "74.4"]);
    expect(within(row).getByRole("rowheader")).toHaveTextContent(
      "Bijan RobinsonRB · ATL",
    );
  });

  it("is a captioned table with a header for every column", () => {
    render(<RankingsTable caption={CAPTION} players={[makePlayerValue()]} />);

    const table = screen.getByRole("table", { name: CAPTION });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((header) => header.textContent),
    ).toEqual([
      "Rank",
      "Player",
      "Proj. ptsProjected points",
      "Valuepts over replacement",
    ]);
  });

  it("scales each value bar to the top value on the page", () => {
    render(
      <RankingsTable
        caption={CAPTION}
        players={[
          makePlayerValue({ player_id: "a", value: 80 }),
          makePlayerValue({ player_id: "b", value: 20 }),
        ]}
      />,
    );

    expect(
      screen.getAllByTestId("value-bar").map((bar) => bar.style.width),
    ).toEqual(["100%", "25%"]);
  });

  it("marks a player without a team as a free agent", () => {
    render(
      <RankingsTable
        caption={CAPTION}
        players={[makePlayerValue({ position: "TE", team: null })]}
      />,
    );

    expect(screen.getByText("TE · FA")).toBeInTheDocument();
  });

  it("shows a dash for a player the model doesn't rank", () => {
    render(
      <RankingsTable
        caption={CAPTION}
        players={[makePlayerValue({ overall_rank: null })]}
      />,
    );

    expect(screen.getAllByRole("cell")[0]).toHaveTextContent("—");
  });
});

describe("valueShare", () => {
  it.each([
    { value: 50, top: 100, share: 0.5 },
    { value: 0, top: 100, share: 0 },
    { value: 10, top: 0, share: 0 },
    { value: -5, top: 100, share: 0 },
    { value: 150, top: 100, share: 1 },
  ])("is $share for $value of $top", ({ value, top, share }) => {
    expect(valueShare(value, top)).toBe(share);
  });
});
