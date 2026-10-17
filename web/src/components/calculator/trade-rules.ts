import type { components } from "@/lib/api/schema";

/** A player as the search returns him: enough to show him and to send his id back. */
export type PlayerRef = components["schemas"]["PlayerRef"];

/** The team that RECEIVES a group of players; matches the API's receives_a / receives_b. */
export type TradeSide = "a" | "b";

export type TradePicks = Record<TradeSide, readonly PlayerRef[]>;

/** The API refuses a side with more players than this (TradeEvaluateRequest). */
export const MAX_PLAYERS_PER_SIDE = 10;

export const TEAM_NAME: Record<TradeSide, string> = {
  a: "Team A",
  b: "Team B",
};

/** Each side's colour: gold for A, violet for B. Always paired with the team's name. */
export const SIDE_DOT: Record<TradeSide, string> = {
  a: "bg-gold",
  b: "bg-violet",
};

/** Which side a player is already on, if any. */
export function sideOf(playerId: string, picks: TradePicks): TradeSide | null {
  if (picks.a.some((player) => player.player_id === playerId)) return "a";
  if (picks.b.some((player) => player.player_id === playerId)) return "b";
  return null;
}

/**
 * Why `player` can't join `side`, in words for the user, or null when he can. These mirror
 * the API's own validation, so the user learns the reason the moment they try instead of
 * from a failed evaluation later.
 */
export function pickRejection(
  player: PlayerRef,
  side: TradeSide,
  picks: TradePicks,
): string | null {
  const current = sideOf(player.player_id, picks);
  if (current === side) {
    return `${player.name} is already on ${TEAM_NAME[side]}'s side.`;
  }
  if (current !== null) {
    return `${player.name} is already on ${TEAM_NAME[current]}'s side. A player can only be on one side of a trade.`;
  }
  if (picks[side].length >= MAX_PLAYERS_PER_SIDE) {
    return `${TEAM_NAME[side]}'s side is full: a side can hold at most ${MAX_PLAYERS_PER_SIDE} players. Remove one to add another.`;
  }
  return null;
}
