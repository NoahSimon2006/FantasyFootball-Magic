import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PlayerPicker } from "./player-picker";
import { SEARCH_DEBOUNCE_MS } from "./player-search";
import { fakeApiClient, makePlayer, makePlayers } from "./test-factories";
import type { PlayerRef, TradePicks } from "./trade-rules";

const CHASE = makePlayer();
const JEFFERSON = makePlayer({
  player_id: "6794",
  name: "Justin Jefferson",
  team: "MIN",
});
const JACKSON = makePlayer({
  player_id: "4881",
  name: "Lamar Jackson",
  position: "QB",
  team: "BAL",
});

/** A search API that returns `players` for any query. */
function searchApi(players: PlayerRef[]) {
  return fakeApiClient(() => Response.json({ players }));
}

function renderPicker({
  picks = { a: [], b: [] },
  players = [CHASE, JEFFERSON, JACKSON],
}: { picks?: TradePicks; players?: PlayerRef[] } = {}) {
  const api = searchApi(players);
  const onAdd = vi.fn();
  const onRemove = vi.fn();
  render(
    <PlayerPicker
      side="a"
      picks={picks}
      onAdd={onAdd}
      onRemove={onRemove}
      client={api.client}
    />,
  );
  return { requests: api.requests, onAdd, onRemove };
}

function searchBox() {
  return screen.getByRole("combobox", { name: "Add a player to Team A" });
}

function type(text: string) {
  fireEvent.change(searchBox(), { target: { value: text } });
}

/** Moves fake time forward and lets the (fake) API respond inside act(). */
async function wait(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  // Only the debounce timer is faked; promises and the fake fetch run normally.
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("PlayerPicker search", () => {
  it("waits for typing to pause, then searches once with the latest text", async () => {
    const { requests } = renderPicker();

    type("ja");
    await wait(SEARCH_DEBOUNCE_MS - 50);
    type("jam");
    await wait(SEARCH_DEBOUNCE_MS - 1);
    expect(requests).toHaveLength(0);

    await wait(1);
    expect(requests.map((request) => request.url)).toEqual([
      "http://api.test/api/v1/players?q=jam&limit=8",
    ]);
  });

  it("doesn't search until at least two letters are typed", async () => {
    const { requests } = renderPicker();

    type("j");
    await wait(1000);

    expect(requests).toHaveLength(0);
    expect(
      screen.getByText("Type at least 2 letters to search."),
    ).toBeInTheDocument();
  });

  it("adds the highlighted player with the arrow keys and Enter", async () => {
    const { onAdd } = renderPicker();

    type("ja");
    await wait(SEARCH_DEBOUNCE_MS);
    // The top match starts highlighted; ArrowDown moves to the second.
    fireEvent.keyDown(searchBox(), { key: "ArrowDown" });
    expect(
      screen.getByRole("option", { name: /Justin Jefferson/ }),
    ).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(searchBox(), { key: "Enter" });

    expect(onAdd).toHaveBeenCalledExactlyOnceWith(JEFFERSON);
    expect(searchBox()).toHaveValue("");
  });

  it("closes the list on Escape", async () => {
    renderPicker();
    type("ja");
    await wait(SEARCH_DEBOUNCE_MS);
    expect(searchBox()).toHaveAttribute("aria-expanded", "true");

    fireEvent.keyDown(searchBox(), { key: "Escape" });

    expect(searchBox()).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("says so when no players match", async () => {
    renderPicker({ players: [] });

    type("zz");
    await wait(SEARCH_DEBOUNCE_MS);

    expect(screen.getByText("No players match “zz”.")).toBeInTheDocument();
  });

  it("says so when the search request fails", async () => {
    const api = fakeApiClient(() => {
      throw new TypeError("Failed to fetch");
    });
    render(
      <PlayerPicker
        side="a"
        picks={{ a: [], b: [] }}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
        client={api.client}
      />,
    );

    type("ja");
    await wait(SEARCH_DEBOUNCE_MS);

    expect(
      screen.getByText(
        "Player search isn't responding. Edit the name to try again.",
      ),
    ).toBeInTheDocument();
  });
});

describe("PlayerPicker trade rules", () => {
  it("refuses a player already on the other side and says why", async () => {
    const { onAdd } = renderPicker({ picks: { a: [], b: [JACKSON] } });

    type("ja");
    await wait(SEARCH_DEBOUNCE_MS);
    fireEvent.click(screen.getByRole("option", { name: /Lamar Jackson/ }));

    expect(onAdd).not.toHaveBeenCalled();
    expect(
      screen.getByText(
        "Lamar Jackson is already on Team B's side. A player can only be on one side of a trade.",
      ),
    ).toBeInTheDocument();
  });

  it("marks players already in the trade in the results", async () => {
    renderPicker({ picks: { a: [CHASE], b: [JACKSON] } });

    type("ja");
    await wait(SEARCH_DEBOUNCE_MS);

    expect(
      screen.getByRole("option", { name: /Ja'Marr Chase.*Added/ }),
    ).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByRole("option", { name: /Lamar Jackson.*On Team B/ }),
    ).toHaveAttribute("aria-disabled", "true");
  });

  it("stops taking players at 10 per side and explains the limit", async () => {
    const { requests } = renderPicker({
      picks: { a: makePlayers(10), b: [] },
    });

    type("ja");
    await wait(SEARCH_DEBOUNCE_MS);

    expect(searchBox()).toHaveAttribute("aria-disabled", "true");
    expect(searchBox()).toHaveAttribute("readonly");
    expect(
      screen.getByText(
        "Team A's side is full: a side can hold at most 10 players. Remove one to add another.",
      ),
    ).toBeInTheDocument();
    expect(requests).toHaveLength(0);
  });

  it("removes a player and keeps keyboard focus in the search", () => {
    const { onRemove } = renderPicker({ picks: { a: [CHASE], b: [] } });

    fireEvent.click(
      screen.getByRole("button", { name: "Remove Ja'Marr Chase from Team A" }),
    );

    expect(onRemove).toHaveBeenCalledExactlyOnceWith(CHASE.player_id);
    expect(searchBox()).toHaveFocus();
  });
});
