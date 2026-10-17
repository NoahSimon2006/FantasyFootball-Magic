import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { makeTrendingResponse } from "./fixtures";
import { TrendingView } from "./trending-view";
import type { MoversHistory } from "./types";

const READY: MoversHistory = {
  kind: "ready",
  snapshotDate: "2026-10-14",
  comparedTo: "2026-10-07",
};

/** The trending answer while history is too short: no dates, no movers. */
const SHORT_HISTORY = makeTrendingResponse({
  snapshot_date: null,
  compared_to: null,
  risers: [],
  fallers: [],
});

function renderView(props: Partial<ComponentProps<typeof TrendingView>> = {}) {
  return render(
    <TrendingView
      result={{
        kind: "ok",
        data: { trending: makeTrendingResponse(), history: READY },
      }}
      days={7}
      search={{}}
      {...props}
    />,
  );
}

function headings() {
  return screen.getAllByRole("heading").map((heading) => heading.textContent);
}

describe("TrendingView", () => {
  it("explains that nothing has been loaded yet when the API has no values", () => {
    renderView({ result: { kind: "unavailable" } });

    expect(
      screen.getByRole("heading", { name: "Trending isn’t available yet" }),
    ).toBeInTheDocument();
  });

  it("offers a retry that reloads the same view when the API is unreachable", () => {
    renderView({ result: { kind: "error" }, search: { days: "14" } });

    expect(screen.getByRole("link", { name: "Try again" })).toHaveAttribute(
      "href",
      "/trending?days=14",
    );
  });

  it("shows most traded, risers, and fallers once history is ready", () => {
    renderView();

    expect(headings()).toEqual(["Most traded", "Risers", "Fallers"]);
  });

  it("says which two snapshots risers and fallers compare", () => {
    renderView();

    expect(screen.getByText(/Value changes since/).textContent).toBe(
      "Value changes since Oct 7, 2026, using projections from Oct 14, 2026.",
    );
  });

  it("explains the wait for history instead of showing empty risers and fallers", () => {
    renderView({
      result: {
        kind: "ok",
        data: {
          trending: SHORT_HISTORY,
          history: { kind: "building", latestSnapshot: "2026-10-14" },
        },
      },
    });

    expect(headings()).toEqual([
      "Most traded",
      "Risers and fallers are still building history",
    ]);
  });

  it("says how far apart the snapshots must be, and when the lists fill in", () => {
    renderView({
      days: 14,
      result: {
        kind: "ok",
        data: {
          trending: SHORT_HISTORY,
          history: { kind: "building", latestSnapshot: null },
        },
      },
    });

    expect(screen.getByText(/at least 14 days earlier/).textContent).toMatch(
      /over the first two weeks of data\.$/,
    );
  });

  it("shows the latest snapshot date while history builds, when it's known", () => {
    renderView({
      result: {
        kind: "ok",
        data: {
          trending: SHORT_HISTORY,
          history: { kind: "building", latestSnapshot: "2026-10-14" },
        },
      },
    });

    expect(screen.getByText("Oct 14, 2026")).toHaveAttribute(
      "datetime",
      "2026-10-14",
    );
  });

  it("keeps showing most-traded players while history builds", () => {
    renderView({
      result: {
        kind: "ok",
        data: {
          trending: SHORT_HISTORY,
          history: { kind: "building", latestSnapshot: null },
        },
      },
    });

    expect(
      screen.getByRole("rowheader", { name: /Patrick Mahomes/ }),
    ).toBeInTheDocument();
  });

  it("says values aren't loaded when there are no projections to compare", () => {
    renderView({
      result: {
        kind: "ok",
        data: { trending: SHORT_HISTORY, history: { kind: "no-projections" } },
      },
    });

    expect(
      screen.getByRole("heading", {
        name: "Risers and fallers need values, and none are loaded yet",
      }),
    ).toBeInTheDocument();
  });

  it("says when no trades were recorded in the window", () => {
    renderView({
      result: {
        kind: "ok",
        data: {
          trending: makeTrendingResponse({ most_traded: [] }),
          history: READY,
        },
      },
    });

    expect(
      screen.getByText("No redraft trades recorded in the last 7 days yet."),
    ).toBeInTheDocument();
  });

  it("says when no player gained value over the window", () => {
    renderView({
      result: {
        kind: "ok",
        data: {
          trending: makeTrendingResponse({ risers: [] }),
          history: READY,
        },
      },
    });

    expect(
      screen.getByText("No player gained value over this window."),
    ).toBeInTheDocument();
  });

  it("credits Sleeper as the source of the data", () => {
    renderView();

    expect(screen.getByText(/public Sleeper leagues/)).toBeInTheDocument();
  });
});
