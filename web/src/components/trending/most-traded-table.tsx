import { formatCount } from "@/components/rankings/format";
import { PlayerName } from "@/components/rankings/player-name";
import {
  TABLE_CELL_CLASSES as CELL_CLASSES,
  TABLE_FRAME_CLASSES,
  TABLE_HEAD_CLASSES as HEAD_CLASSES,
} from "@/components/rankings/styles";

import { Delta } from "./delta";
import type { TradedPlayer } from "./types";

/** Redraft trade counts this window next to the window before, with the change between. */
export function MostTradedTable({
  players,
  days,
}: {
  players: readonly TradedPlayer[];
  days: number;
}) {
  const caption = `Most traded players: redraft trades in the last ${days} days and the ${days} days before`;
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
            <th scope="col" className={HEAD_CLASSES}>
              Player
            </th>
            <th scope="col" className={`${HEAD_CLASSES} text-right`}>
              Last {days} days
            </th>
            <th scope="col" className={`${HEAD_CLASSES} text-right`}>
              {days} days before
            </th>
            <th scope="col" className={`${HEAD_CLASSES} text-right`}>
              Change
            </th>
          </tr>
        </thead>
        <tbody>
          {players.map((row) => (
            <tr key={row.player.player_id} className="border-t border-rule">
              <th scope="row" className={`${CELL_CLASSES} font-normal`}>
                <PlayerName player={row.player} />
              </th>
              <td
                className={`${CELL_CLASSES} text-right font-semibold text-ink`}
              >
                {formatCount(row.trades)}
              </td>
              <td className={`${CELL_CLASSES} text-right text-ink-muted`}>
                {formatCount(row.previous_trades)}
              </td>
              <td className={`${CELL_CLASSES} text-right`}>
                <Delta change={row.change} unit="trades" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
