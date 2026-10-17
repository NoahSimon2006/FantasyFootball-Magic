import { formatPoints } from "./format";
import { PlayerName } from "./player-name";
import {
  TABLE_CELL_CLASSES as CELL_CLASSES,
  TABLE_FRAME_CLASSES,
  TABLE_HEAD_CLASSES as HEAD_CLASSES,
} from "./styles";
import type { PlayerValue } from "./types";

/** Bar length as a share of the page's top value, kept within 0–1. */
export function valueShare(value: number, topValue: number): number {
  if (topValue <= 0) return 0;
  return Math.min(1, Math.max(0, value / topValue));
}

/**
 * One page of ranked players. Each value gets a gold bar on a shared left baseline
 * (replacement level, value 0), so the drop-offs between tiers read at a glance. The bar is
 * decoration only: the number beside it carries the value.
 */
export function RankingsTable({
  players,
  caption,
}: {
  players: readonly PlayerValue[];
  caption: string;
}) {
  const topValue = Math.max(0, ...players.map((player) => player.value));

  return (
    <div
      role="region"
      aria-label={caption}
      tabIndex={0}
      className={TABLE_FRAME_CLASSES}
    >
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className={`${HEAD_CLASSES} w-12 text-right`}>
              Rank
            </th>
            <th scope="col" className={HEAD_CLASSES}>
              Player
            </th>
            <th scope="col" className={`${HEAD_CLASSES} text-right`}>
              <span aria-hidden="true">Proj. pts</span>
              <span className="sr-only">Projected points</span>
            </th>
            <th scope="col" className={HEAD_CLASSES}>
              Value
              <span className="block text-[0.6875rem] font-medium tracking-normal normal-case">
                pts over replacement
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => (
            <tr
              key={player.player_id}
              className="border-t border-rule hover:bg-well/40"
            >
              <td className={`${CELL_CLASSES} text-right text-ink-muted`}>
                {player.overall_rank ?? "—"}
              </td>
              <th scope="row" className={`${CELL_CLASSES} font-normal`}>
                <PlayerName player={player} />
              </th>
              <td className={`${CELL_CLASSES} text-right`}>
                {formatPoints(player.ros_points)}
              </td>
              <td className={CELL_CLASSES}>
                <div className="flex flex-col items-start gap-1.5 sm:flex-row sm:items-center sm:gap-3">
                  <span
                    aria-hidden="true"
                    className="block h-2 w-20 shrink-0 overflow-hidden rounded-full bg-well sm:w-40"
                  >
                    <span
                      data-testid="value-bar"
                      className="block h-full rounded-full bg-gold"
                      style={{
                        width: `${(valueShare(player.value, topValue) * 100).toFixed(1)}%`,
                      }}
                    />
                  </span>
                  <span className="font-semibold text-ink">
                    {formatPoints(player.value)}
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
