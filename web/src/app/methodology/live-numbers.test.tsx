import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Methodology } from "./data";
import { describeLineup, LiveNumbers } from "./live-numbers";

const METHODOLOGY: Methodology = {
  model: "projection_vor_v0",
  parameters: {
    depth_decay: 0.85,
    even_threshold: 0.05,
    last_fantasy_week: 17,
    valued_positions: ["QB", "RB", "WR", "TE"],
    default_teams: 12,
    default_ppr: 1,
    lineup_1qb: { slots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1 } },
    lineup_superflex: {
      slots: { SUPER_FLEX: 1, QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1 },
    },
  },
  data: {
    latest_projection_snapshot: "2026-10-15",
    projection_snapshots: 1,
    players: 4266,
    leagues: 0,
    trades: 0,
  },
};

describe("LiveNumbers", () => {
  it("shows the model's settings as readable sentences", () => {
    render(<LiveNumbers result={{ kind: "ok", data: METHODOLOGY }} />);

    const settings = screen.getByRole("region", { name: "Settings in use" });
    expect(
      within(settings).getByText(/counts 85% of the one before/),
    ).toBeInTheDocument();
    expect(
      within(settings).getByText(/gaps under 5% of the larger side/),
    ).toBeInTheDocument();
    expect(within(settings).getByText(/through week 17/)).toBeInTheDocument();
  });

  it("shows how much data stands behind the numbers", () => {
    render(<LiveNumbers result={{ kind: "ok", data: METHODOLOGY }} />);

    const data = screen.getByRole("region", { name: "Data behind them" });
    expect(within(data).getByText("2026-10-15")).toBeInTheDocument();
    expect(within(data).getByText("4,266")).toBeInTheDocument();
  });

  it("says plainly when no projections are loaded yet", () => {
    const empty = {
      ...METHODOLOGY,
      data: { ...METHODOLOGY.data, latest_projection_snapshot: null },
    };

    render(<LiveNumbers result={{ kind: "ok", data: empty }} />);

    expect(screen.getByText("none loaded yet")).toBeInTheDocument();
  });

  it("explains an unreachable API instead of breaking the page", () => {
    render(<LiveNumbers result={{ kind: "error" }} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Live numbers unavailable",
    );
  });
});

describe("describeLineup", () => {
  it("lists slots in lineup order with readable flex names", () => {
    expect(
      describeLineup({ SUPER_FLEX: 1, FLEX: 1, TE: 1, WR: 2, RB: 2, QB: 1 }),
    ).toBe("QB 1 · RB 2 · WR 2 · TE 1 · FLEX 1 · Superflex 1");
  });

  it("skips empty slots and puts unknown codes last", () => {
    expect(describeLineup({ IDP_FLEX: 1, QB: 1, FLEX: 0 })).toBe(
      "QB 1 · IDP_FLEX 1",
    );
  });
});
