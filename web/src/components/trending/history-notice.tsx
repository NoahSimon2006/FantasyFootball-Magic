import { formatDate } from "@/components/rankings/format";
import { StatePanel } from "@/components/rankings/state-panel";

import type { MoversHistory } from "./types";

function spanLabel(days: number): string {
  if (days === 7) return "week";
  if (days === 14) return "two weeks";
  return `${days} days`;
}

/**
 * Stands in for risers and fallers until they can exist. During the first week of data this
 * is the normal state, so it explains the wait rather than looking like an error.
 */
export function HistoryNotice({
  history,
  days,
}: {
  history: Exclude<MoversHistory, { kind: "ready" }>;
  days: number;
}) {
  if (history.kind === "no-projections") {
    return (
      <StatePanel title="Risers and fallers need values, and none are loaded yet">
        <p>
          They track how each player’s projection changes, and no projections
          have been loaded to value players with. The most-traded counts don’t
          need projections, so they show up as soon as trades are loaded.
        </p>
      </StatePanel>
    );
  }

  return (
    <StatePanel title="Risers and fallers are still building history">
      <p>
        They compare each player’s projected points now with his projection at
        least {days} days earlier, so they need two projection snapshots that
        far apart. Projections are saved as one snapshot per day, so these lists
        fill in over the first {spanLabel(days)} of data.
      </p>
      {history.latestSnapshot ? (
        <p>
          Latest projections:{" "}
          <time dateTime={history.latestSnapshot}>
            {formatDate(history.latestSnapshot)}
          </time>
          .
        </p>
      ) : null}
    </StatePanel>
  );
}
