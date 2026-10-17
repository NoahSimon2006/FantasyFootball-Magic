import type { components } from "@/lib/api/schema";

type PlayerLabel = Pick<
  components["schemas"]["PlayerRef"],
  "name" | "position" | "team"
>;

/**
 * A player's name over "WR · CIN" (shared with /trending). A player with a position but no
 * team is a free agent. An unknown player (no position) gets no second line.
 */
export function PlayerName({ player }: { player: PlayerLabel }) {
  const details = player.position
    ? `${player.position} · ${player.team ?? "FA"}`
    : null;
  return (
    <>
      <span className="block font-semibold text-ink">{player.name}</span>
      {details ? (
        <span className="block text-xs font-normal text-ink-muted">
          {details}
        </span>
      ) : null}
    </>
  );
}
