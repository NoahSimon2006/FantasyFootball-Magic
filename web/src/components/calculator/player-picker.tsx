"use client";

import { useId, useRef } from "react";

import { browserApi, type ApiClient } from "@/lib/api/client";

import { PlayerSearch } from "./player-search";
import {
  MAX_PLAYERS_PER_SIDE,
  pickRejection,
  SIDE_DOT,
  sideOf,
  TEAM_NAME,
  type PlayerRef,
  type TradePicks,
  type TradeSide,
} from "./trade-rules";

export interface PlayerPickerProps {
  side: TradeSide;
  /** Both sides of the trade: a player can't be added twice or to both sides. */
  picks: TradePicks;
  onAdd: (player: PlayerRef) => void;
  onRemove: (playerId: string) => void;
  /** The API client; tests pass one with a fake fetch. */
  client?: ApiClient;
}

/** One side of the trade: what this team receives, with a search to add players. */
export function PlayerPicker({
  side,
  picks,
  onAdd,
  onRemove,
  client = browserApi,
}: PlayerPickerProps) {
  const headingId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const team = TEAM_NAME[side];
  const players = picks[side];
  const full = players.length >= MAX_PLAYERS_PER_SIDE;

  function handlePick(player: PlayerRef): string | null {
    const refusal = pickRejection(player, side, picks);
    if (refusal === null) onAdd(player);
    return refusal;
  }

  function tagFor(player: PlayerRef): string | null {
    const current = sideOf(player.player_id, picks);
    if (current === null) return null;
    return current === side ? "Added" : `On ${TEAM_NAME[current]}`;
  }

  return (
    <section
      aria-labelledby={headingId}
      className="rounded-2xl border border-rule bg-card p-5 sm:p-6"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2
          id={headingId}
          className="flex items-center gap-2.5 font-display text-2xl font-semibold tracking-tight"
        >
          <span
            aria-hidden="true"
            className={`size-2.5 shrink-0 rounded-full ${SIDE_DOT[side]}`}
          />
          {team} receives
        </h2>
        <p className="text-sm whitespace-nowrap text-ink-muted">
          {players.length} / {MAX_PLAYERS_PER_SIDE} players
        </p>
      </div>

      <div className="mt-4">
        <PlayerSearch
          label={`Add a player to ${team}`}
          client={client}
          onPick={handlePick}
          tagFor={tagFor}
          unavailableReason={
            full
              ? `${team}'s side is full: a side can hold at most ${MAX_PLAYERS_PER_SIDE} players. Remove one to add another.`
              : null
          }
          inputRef={inputRef}
        />
      </div>

      {players.length === 0 ? (
        <p className="mt-2 rounded-xl border border-dashed border-rule px-4 py-5 text-center text-sm text-ink-muted">
          No players yet. Search above to add who {team} gets.
        </p>
      ) : (
        <ul
          aria-label={`${team} receives`}
          className="mt-2 flex flex-wrap gap-2"
        >
          {players.map((player) => (
            <li
              key={player.player_id}
              className="inline-flex items-center gap-2 rounded-full border border-rule bg-well py-1 pr-1 pl-3.5"
            >
              <span className="text-sm font-medium text-ink">
                {player.name}
              </span>
              <span className="text-xs text-ink-muted">
                {player.position} · {player.team ?? "FA"}
              </span>
              <button
                type="button"
                aria-label={`Remove ${player.name} from ${team}`}
                onClick={() => {
                  onRemove(player.player_id);
                  // The button is about to disappear; keep keyboard focus in this side.
                  inputRef.current?.focus();
                }}
                className="grid size-7 place-items-center rounded-full text-ink-muted transition-colors hover:bg-paper hover:text-ink"
              >
                <svg
                  viewBox="0 0 16 16"
                  aria-hidden="true"
                  className="size-3.5"
                >
                  <path
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeWidth="2"
                    d="m4 4 8 8m0-8-8 8"
                  />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
