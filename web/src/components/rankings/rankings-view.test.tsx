import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { makePlayerValue, makeValuesResponse } from "./fixtures";
import { RankingsView } from "./rankings-view";

function renderView(props: Partial<ComponentProps<typeof RankingsView>> = {}) {
  return render(
    <RankingsView
      result={{ kind: "ok", data: makeValuesResponse() }}
      position={undefined}
      offset={0}
      pageSize={50}
      search={{}}
      {...props}
    />,
  );
}

describe("RankingsView", () => {
  it("explains that values haven't been loaded yet when the API has no projections", () => {
    renderView({ result: { kind: "unavailable" } });

    expect(
      screen.getByRole("heading", { name: "Values haven’t been loaded yet" }),
    ).toBeInTheDocument();
  });

  it("says the rankings couldn't load when the API is unreachable", () => {
    renderView({ result: { kind: "error" } });

    expect(
      screen.getByRole("heading", { name: "Rankings couldn’t load" }),
    ).toBeInTheDocument();
  });

  it("offers a retry that reloads the same view", () => {
    renderView({
      result: { kind: "error" },
      search: { teams: "10", position: "QB" },
    });

    expect(screen.getByRole("link", { name: "Try again" })).toHaveAttribute(
      "href",
      "/rankings?teams=10&position=QB",
    );
  });

  it("sends a page past the end of the list back to the first page", () => {
    renderView({
      result: {
        kind: "ok",
        data: makeValuesResponse({ players: [], total: 312 }),
      },
      offset: 400,
      search: { offset: "400", ppr: "0" },
    });

    expect(
      screen.getByRole("link", { name: "Go to the first page" }),
    ).toHaveAttribute("href", "/rankings?ppr=0");
  });

  it("offers every position when a position filter matches no one", () => {
    renderView({
      result: {
        kind: "ok",
        data: makeValuesResponse({ players: [], total: 0 }),
      },
      position: "TE",
      search: { position: "TE", teams: "14" },
    });

    expect(
      screen.getByRole("heading", { name: "No tight ends ranked yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Show all positions" }),
    ).toHaveAttribute("href", "/rankings?teams=14");
  });

  it("says when the latest projections hold no rankable players", () => {
    renderView({
      result: {
        kind: "ok",
        data: makeValuesResponse({ players: [], total: 0 }),
      },
    });

    expect(
      screen.getByRole("heading", { name: "No players ranked yet" }),
    ).toBeInTheDocument();
  });

  it("shows the snapshot date and the weeks the values cover", () => {
    renderView({
      result: {
        kind: "ok",
        data: makeValuesResponse({
          snapshot_date: "2026-10-14",
          from_week: 7,
          through_week: 17,
        }),
      },
    });

    const date = screen.getByText("Oct 14, 2026");
    expect([
      date.tagName,
      date.getAttribute("datetime"),
      date.parentElement?.textContent,
    ]).toEqual([
      "TIME",
      "2026-10-14",
      expect.stringContaining("Values use projections for weeks 7–17"),
    ]);
  });

  it("captions the table with the format and the slice of the list it shows", () => {
    renderView({
      result: {
        kind: "ok",
        data: makeValuesResponse({
          league_format: { teams: 10, ppr: 0.5, superflex: true },
          players: [
            makePlayerValue({ player_id: "a" }),
            makePlayerValue({ player_id: "b" }),
          ],
          total: 52,
        }),
      },
      position: "WR",
      offset: 50,
    });

    expect(
      screen.getByRole("table", {
        name: "Ranked wide receivers for 10-team · Half PPR · Superflex, 51 to 52 of 52",
      }),
    ).toBeInTheDocument();
  });

  it("explains value in plain English, including that v0 uses projections only", () => {
    renderView();

    expect(
      screen.getByRole("heading", { name: "What “value” means" }),
    ).toBeInTheDocument();
    expect(screen.getByText("v0: projections only")).toBeInTheDocument();
  });
});
