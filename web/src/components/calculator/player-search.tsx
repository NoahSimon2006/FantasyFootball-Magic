"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type Ref,
} from "react";

import { Chip } from "@/components/ui/chip";
import type { ApiClient } from "@/lib/api/client";

import type { PlayerRef } from "./trade-rules";

/** Search once typing pauses this long: one request per pause, not one per keystroke. */
export const SEARCH_DEBOUNCE_MS = 250;
/** The API's minimum query length for GET /api/v1/players. */
export const MIN_QUERY_LENGTH = 2;
const RESULT_LIMIT = 8;

type SearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "done"; players: PlayerRef[] }
  | { status: "error" };

interface Notice {
  tone: "info" | "warning";
  text: string;
}

export interface PlayerSearchProps {
  /** The visible label, which is also the combobox's accessible name. */
  label: string;
  client: ApiClient;
  /** The user chose `player`. Return a sentence to refuse the pick (it is shown), or null. */
  onPick: (player: PlayerRef) => string | null;
  /** A short tag for a player who is already in the trade ("On Team B"), or null. */
  tagFor?: (player: PlayerRef) => string | null;
  /** When set, the search is read-only and this sentence says why. */
  unavailableReason?: string | null;
  inputRef?: Ref<HTMLInputElement>;
}

/**
 * A player-name typeahead following the ARIA combobox pattern: the input keeps focus, the
 * highlighted option is announced through aria-activedescendant, ArrowUp/ArrowDown move,
 * Enter adds, Escape closes the list (or clears the text if it's already closed).
 */
export function PlayerSearch({
  label,
  client,
  onPick,
  tagFor,
  unavailableReason = null,
  inputRef,
}: PlayerSearchProps) {
  const id = useId();
  const inputId = `${id}-input`;
  const listId = `${id}-list`;
  const statusId = `${id}-status`;
  const optionId = (index: number) => `${id}-option-${index}`;

  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchState>({ status: "idle" });
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [notice, setNotice] = useState<Notice | null>(null);

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const inFlight = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Drop a pending or running search when the picker unmounts (or its route is hidden).
  useEffect(
    () => () => {
      clearTimeout(debounceTimer.current);
      inFlight.current?.abort();
    },
    [],
  );

  // Keep the keyboard-highlighted option visible inside the scrolling list.
  useEffect(() => {
    if (activeIndex < 0) return;
    // Optional call: jsdom (tests) has no scrollIntoView.
    listRef.current?.children[activeIndex]?.scrollIntoView?.({
      block: "nearest",
    });
  }, [activeIndex]);

  const unavailable = unavailableReason !== null;
  const players = search.status === "done" ? search.players : [];
  const expanded = open && !unavailable && players.length > 0;
  const trimmed = query.trim();

  async function runSearch(q: string) {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const { data } = await client.GET("/api/v1/players", {
        params: { query: { q, limit: RESULT_LIMIT } },
        signal: controller.signal,
      });
      if (controller.signal.aborted) return; // a newer query took over
      if (data === undefined) {
        setSearch({ status: "error" });
        return;
      }
      setSearch({ status: "done", players: data.players });
      // Highlight the top match so "type a name, press Enter" works.
      setActiveIndex(data.players.length > 0 ? 0 : -1);
    } catch {
      if (!controller.signal.aborted) setSearch({ status: "error" });
    }
  }

  function handleChange(value: string) {
    // readOnly stops typing, not programmatic change events; never search a full side.
    if (unavailable) return;
    setQuery(value);
    setNotice(null);
    setOpen(true);
    setActiveIndex(-1);
    clearTimeout(debounceTimer.current);
    inFlight.current?.abort();
    const q = value.trim();
    if (q.length < MIN_QUERY_LENGTH) {
      setSearch({ status: "idle" });
      return;
    }
    setSearch({ status: "loading" });
    debounceTimer.current = setTimeout(
      () => void runSearch(q),
      SEARCH_DEBOUNCE_MS,
    );
  }

  function choose(player: PlayerRef) {
    const refusal = onPick(player);
    if (refusal !== null) {
      // Keep the list open so another player can be chosen right away.
      setNotice({ tone: "warning", text: refusal });
      return;
    }
    setQuery("");
    setSearch({ status: "idle" });
    setOpen(false);
    setActiveIndex(-1);
    setNotice({ tone: "info", text: `Added ${player.name}.` });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp": {
        if (unavailable || players.length === 0) return;
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        setOpen(true);
        // Reopening keeps the highlight; otherwise move it, wrapping at either end.
        setActiveIndex((index) =>
          !expanded
            ? Math.max(index, 0)
            : (index + step + players.length) % players.length,
        );
        return;
      }
      case "Enter": {
        const player = expanded ? players[activeIndex] : undefined;
        if (player === undefined) return;
        event.preventDefault();
        choose(player);
        return;
      }
      case "Escape":
        if (expanded) {
          event.preventDefault();
          setOpen(false);
        } else if (query !== "") {
          event.preventDefault();
          handleChange("");
        }
        return;
    }
  }

  let status: Notice | null = notice;
  if (unavailableReason !== null) {
    status = { tone: "warning", text: unavailableReason };
  } else if (status === null) {
    switch (search.status) {
      case "idle":
        status =
          trimmed.length > 0
            ? {
                tone: "info",
                text: `Type at least ${MIN_QUERY_LENGTH} letters to search.`,
              }
            : null;
        break;
      case "loading":
        status = { tone: "info", text: "Searching…" };
        break;
      case "error":
        status = {
          tone: "warning",
          text: "Player search isn't responding. Edit the name to try again.",
        };
        break;
      case "done":
        status = {
          tone: "info",
          text:
            players.length === 0
              ? `No players match “${trimmed}”.`
              : `${players.length} ${players.length === 1 ? "match" : "matches"}. Use ↑ and ↓ to choose, Enter to add.`,
        };
        break;
    }
  }

  return (
    <div>
      <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <div className="relative">
        <svg
          viewBox="0 0 20 20"
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-faint"
        >
          <path
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2"
            d="m17 17-4-4m1.5-4.5a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z"
          />
        </svg>
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            expanded && activeIndex >= 0 ? optionId(activeIndex) : undefined
          }
          aria-describedby={statusId}
          // Read-only rather than disabled when the side is full, so focus isn't thrown
          // out of the field the moment the tenth player is added.
          aria-disabled={unavailable || undefined}
          readOnly={unavailable}
          autoComplete="off"
          spellCheck={false}
          placeholder={unavailable ? "This side is full" : "Search by name"}
          value={query}
          onChange={(event) => handleChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          className="h-11 w-full rounded-lg border border-rule-strong bg-well pr-3 pl-9 text-base text-ink placeholder:text-ink-faint aria-disabled:cursor-not-allowed aria-disabled:opacity-70"
        />
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          aria-label="Matching players"
          hidden={!expanded}
          className="absolute inset-x-0 top-full z-20 mt-1.5 max-h-72 overflow-y-auto rounded-xl border border-rule bg-card p-1 shadow-xl shadow-black/10"
        >
          {players.map((player, index) => {
            const tag = tagFor?.(player) ?? null;
            return (
              <li
                key={player.player_id}
                id={optionId(index)}
                role="option"
                aria-selected={index === activeIndex}
                aria-disabled={tag !== null || undefined}
                // mousedown would blur the input (closing the list) before the click lands.
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => choose(player)}
                className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border-l-2 border-transparent px-3 py-2 aria-disabled:cursor-default aria-selected:border-gold aria-selected:bg-gold-soft"
              >
                <span className="min-w-0">
                  <span
                    className={`block truncate font-medium ${tag === null ? "text-ink" : "text-ink-muted"}`}
                  >
                    {player.name}
                  </span>
                  <span className="block text-xs text-ink-muted">
                    {player.position} · {player.team ?? "Free agent"}
                  </span>
                </span>
                {tag !== null ? <Chip>{tag}</Chip> : null}
              </li>
            );
          })}
        </ul>
      </div>
      <p
        id={statusId}
        role="status"
        className={`mt-1.5 min-h-5 text-sm ${status?.tone === "warning" ? "text-negative" : "text-ink-muted"}`}
      >
        {status?.text}
      </p>
    </div>
  );
}
