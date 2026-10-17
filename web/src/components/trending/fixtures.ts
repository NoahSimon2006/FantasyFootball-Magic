// Test data factories for /trending, typed with the generated API types.
import type { components } from "@/lib/api/schema";

import type { TradedPlayer, TrendingResponse, ValueMove } from "./types";

type PlayerRef = components["schemas"]["PlayerRef"];

export function makePlayerRef(overrides: Partial<PlayerRef> = {}): PlayerRef {
  return {
    player_id: "4046",
    name: "Patrick Mahomes",
    position: "QB",
    team: "KC",
    ...overrides,
  };
}

export function makeTradedPlayer(
  overrides: Partial<TradedPlayer> = {},
): TradedPlayer {
  return {
    player: makePlayerRef(),
    trades: 12,
    previous_trades: 8,
    change: 4,
    ...overrides,
  };
}

export function makeValueMove(overrides: Partial<ValueMove> = {}): ValueMove {
  return {
    player: makePlayerRef({ player_id: "9509", name: "Bijan Robinson" }),
    value_now: 41.2,
    value_then: 35.0,
    change: 6.2,
    ros_points_now: 182.4,
    ros_points_then: 171.0,
    points_change: 11.4,
    ...overrides,
  };
}

/** Defaults to the "history ready" shape: both snapshot dates present. */
export function makeTrendingResponse(
  overrides: Partial<TrendingResponse> = {},
): TrendingResponse {
  return {
    days: 7,
    league_format: { teams: 12, ppr: 1, superflex: false },
    most_traded: [makeTradedPlayer()],
    snapshot_date: "2026-10-14",
    compared_to: "2026-10-07",
    risers: [makeValueMove()],
    fallers: [
      makeValueMove({
        player: makePlayerRef({ player_id: "6794", name: "Justin Jefferson" }),
        value_now: 52.0,
        value_then: 60.5,
        change: -8.5,
        ros_points_now: 190.2,
        ros_points_then: 201.0,
        points_change: -10.8,
      }),
    ],
    ...overrides,
  };
}
