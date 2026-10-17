// Test data factories for /rankings (and the shared values shape /trending probes). Typed
// with the generated API types, so a schema change breaks the fixtures at compile time.
import type { PlayerValue, ValuesResponse } from "./types";

export function makePlayerValue(
  overrides: Partial<PlayerValue> = {},
): PlayerValue {
  return {
    player_id: "7564",
    name: "Ja'Marr Chase",
    position: "WR",
    team: "CIN",
    ros_points: 231.4,
    value: 98.2,
    overall_rank: 1,
    position_rank: 1,
    ...overrides,
  };
}

export function makeValuesResponse(
  overrides: Partial<ValuesResponse> = {},
): ValuesResponse {
  return {
    snapshot_date: "2026-10-14",
    season: 2026,
    from_week: 7,
    through_week: 17,
    league_format: { teams: 12, ppr: 1, superflex: false },
    total: 312,
    players: [makePlayerValue()],
    ...overrides,
  };
}

/** An API error body in the API's single error shape. */
export function makeApiError(code: string, message = "test error") {
  return { error: { code, message } };
}
