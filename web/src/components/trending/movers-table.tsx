import { formatPoints } from "@/components/rankings/format";
import { PlayerName } from "@/components/rankings/player-name";
import {
  TABLE_CELL_CLASSES as CELL_CLASSES,
  TABLE_FRAME_CLASSES,
  TABLE_HEAD_CLASSES as HEAD_CLASSES,
} from "@/components/rankings/styles";

import { Delta } from "./delta";
import type { ValueMove } from "./types";

/** Risers or fallers: value now over what it was, the signed change, and projected points. */
export function MoversTable({
  moves,
  caption,
}: {
  moves: readonly ValueMove[];
  caption: string;
}) {
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
              Value
            </th>
            <th scope="col" className={`${HEAD_CLASSES} text-right`}>
              Change
            </th>
            <th scope="col" className={`${HEAD_CLASSES} text-right`}>
              <span aria-hidden="true">Proj. pts</span>
              <span className="sr-only">Projected points</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {moves.map((move) => (
            <tr key={move.player.player_id} className="border-t border-rule">
              <th scope="row" className={`${CELL_CLASSES} font-normal`}>
                <PlayerName player={move.player} />
              </th>
              <td className={`${CELL_CLASSES} text-right`}>
                <span className="block font-semibold text-ink">
                  {formatPoints(move.value_now)}
                </span>
                <span className="block text-xs text-ink-muted">
                  was {formatPoints(move.value_then)}
                </span>
              </td>
              <td className={`${CELL_CLASSES} text-right`}>
                <Delta change={move.change} unit="points" />
              </td>
              <td className={`${CELL_CLASSES} text-right`}>
                {formatPoints(move.ros_points_now)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
