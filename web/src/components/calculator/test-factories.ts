// Test data builders and a fake API for the calculator's tests (not used by app code).
import { createApiClient } from "@/lib/api/client";

import type { TradeEvaluation } from "./evaluate-trade";
import type { PlayerRef } from "./trade-rules";

type PlayerValue = TradeEvaluation["side_a"]["players"][number];

export function makePlayer(overrides: Partial<PlayerRef> = {}): PlayerRef {
  return {
    player_id: "7564",
    name: "Ja'Marr Chase",
    position: "WR",
    team: "CIN",
    ...overrides,
  };
}

/** `count` distinct players, e.g. to fill a side. */
export function makePlayers(count: number): PlayerRef[] {
  return Array.from({ length: count }, (_, index) =>
    makePlayer({ player_id: `p${index + 1}`, name: `Player ${index + 1}` }),
  );
}

export function makePlayerValue(
  overrides: Partial<PlayerValue> = {},
): PlayerValue {
  return {
    player_id: "7564",
    name: "Ja'Marr Chase",
    position: "WR",
    team: "CIN",
    ros_points: 180.2,
    value: 60.5,
    overall_rank: 3,
    position_rank: 1,
    ...overrides,
  };
}

/** A 1-for-1 trade that Team A wins by 10.5 value points. */
export function makeEvaluation(
  overrides: Partial<TradeEvaluation> = {},
): TradeEvaluation {
  return {
    side_a: {
      players: [makePlayerValue()],
      raw_total: 60.5,
      adjusted_total: 60.5,
    },
    side_b: {
      players: [
        makePlayerValue({
          player_id: "9509",
          name: "Bijan Robinson",
          position: "RB",
          team: "ATL",
          ros_points: 171.4,
          value: 50,
          overall_rank: 7,
          position_rank: 2,
        }),
      ],
      raw_total: 50,
      adjusted_total: 50,
    },
    verdict: "a",
    margin: 10.5,
    margin_share: 0.1736,
    drivers: [
      {
        kind: "value_gap",
        side: "a",
        amount: 10.5,
        label:
          "Team A receives 10.5 more value points (17% of the larger side)",
      },
    ],
    method: "projection_vor_v0",
    snapshot_date: "2026-10-14",
    league_format: { teams: 12, ppr: 1, superflex: false },
    ...overrides,
  };
}

/** A response in the API's error shape. */
export function apiErrorResponse(
  status: number,
  code: string,
  message: string,
): Response {
  return Response.json({ error: { code, message } }, { status });
}

/** A typed API client whose fetch is `respond`. Records every request it receives. */
export function fakeApiClient(
  respond: (request: Request) => Response | Promise<Response>,
) {
  const requests: Request[] = [];
  const client = createApiClient({
    baseUrl: "http://api.test",
    fetch: async (request: Request) => {
      requests.push(request);
      return respond(request);
    },
  });
  return { client, requests };
}
