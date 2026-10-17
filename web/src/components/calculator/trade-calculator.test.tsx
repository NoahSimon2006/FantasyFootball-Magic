import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_FORMAT } from "@/lib/league-format";

import { SEARCH_DEBOUNCE_MS } from "./player-search";
import {
  apiErrorResponse,
  fakeApiClient,
  makeEvaluation,
  makePlayer,
} from "./test-factories";
import { TradeCalculator } from "./trade-calculator";

const CHASE = makePlayer();
const BIJAN = makePlayer({
  player_id: "9509",
  name: "Bijan Robinson",
  position: "RB",
  team: "ATL",
});
const JEFFERSON = makePlayer({
  player_id: "6794",
  name: "Justin Jefferson",
  team: "MIN",
});

/**
 * A fake API: player search matches names from a small pool, and the trade evaluation
 * answers with `evaluate(request)`.
 */
function renderCalculator(
  evaluate: (request: Request) => Response | Promise<Response>,
) {
  const api = fakeApiClient((request) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/players") {
      const q = (url.searchParams.get("q") ?? "").toLowerCase();
      return Response.json({
        players: [CHASE, BIJAN, JEFFERSON].filter((player) =>
          player.name.toLowerCase().includes(q),
        ),
      });
    }
    return evaluate(request);
  });
  render(<TradeCalculator format={DEFAULT_FORMAT} client={api.client} />);
  return api;
}

/** Moves fake time forward and lets the fake API respond inside act(). */
async function wait(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function addPlayer(team: "Team A" | "Team B", name: string) {
  fireEvent.change(
    screen.getByRole("combobox", { name: `Add a player to ${team}` }),
    { target: { value: name.slice(0, 4) } },
  );
  await wait(SEARCH_DEBOUNCE_MS);
  fireEvent.click(screen.getByRole("option", { name: new RegExp(name) }));
}

function evaluateButton() {
  return screen.getByRole("button", { name: "Evaluate trade" });
}

async function buildTradeAndEvaluate() {
  await addPlayer("Team A", CHASE.name);
  await addPlayer("Team B", BIJAN.name);
  fireEvent.click(evaluateButton());
  await wait(0);
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("TradeCalculator", () => {
  it("enables Evaluate only once both sides have a player", async () => {
    renderCalculator(() => Response.json(makeEvaluation()));
    expect(evaluateButton()).toBeDisabled();

    await addPlayer("Team A", CHASE.name);
    expect(evaluateButton()).toBeDisabled();
    expect(
      screen.getByText("Add at least one player to Team B."),
    ).toBeInTheDocument();

    await addPlayer("Team B", BIJAN.name);
    expect(evaluateButton()).toBeEnabled();
  });

  it("sends both sides in the league format and shows the verdict", async () => {
    const api = renderCalculator(() => Response.json(makeEvaluation()));

    await buildTradeAndEvaluate();

    const request = api.requests.find((r) => r.method === "POST");
    expect(await request?.json()).toEqual({
      receives_a: [CHASE.player_id],
      receives_b: [BIJAN.player_id],
      teams: 12,
      ppr: 1,
      superflex: false,
    });
    expect(
      screen.getByRole("heading", { level: 2, name: "Team A wins" }),
    ).toBeInTheDocument();
  });

  it("marks the verdict out of date when the trade changes afterwards", async () => {
    renderCalculator(() => Response.json(makeEvaluation()));
    await buildTradeAndEvaluate();

    await addPlayer("Team B", JEFFERSON.name);

    expect(
      screen.getByText(
        "The trade or league format has changed since this verdict. Evaluate again to update it.",
      ),
    ).toBeInTheDocument();
  });

  it("explains that values aren't loaded yet when the API answers 503", async () => {
    renderCalculator(() =>
      apiErrorResponse(503, "VALUES_UNAVAILABLE", "no projections ingested"),
    );

    await buildTradeAndEvaluate();

    expect(
      screen.getByRole("heading", { name: "Values aren't loaded yet" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    // An expected state before the first data load, so it isn't raised as an alert.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("names the player the API couldn't value on a 404", async () => {
    renderCalculator(() =>
      apiErrorResponse(
        404,
        "PLAYER_NOT_FOUND",
        `no value for player id(s): ${BIJAN.player_id}`,
      ),
    );

    await buildTradeAndEvaluate();

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Bijan Robinson can't be valued yet",
    );
  });

  it("says the API can't be reached when the request fails", async () => {
    renderCalculator(() => {
      throw new TypeError("Failed to fetch");
    });

    await buildTradeAndEvaluate();

    expect(screen.getByRole("alert")).toHaveTextContent("Can't reach the API");
  });

  it("treats a proxy error page (API down behind the rewrite) as unreachable", async () => {
    renderCalculator(
      () => new Response("Internal Server Error", { status: 500 }),
    );

    await buildTradeAndEvaluate();

    expect(screen.getByRole("alert")).toHaveTextContent("Can't reach the API");
  });
});
