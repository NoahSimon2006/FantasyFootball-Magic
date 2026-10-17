import Link from "next/link";

import { describeFormat } from "@/lib/league-format";

import { formatCount, formatDate } from "./format";
import { hrefWith, type SearchParams } from "./href";
import { Pagination, pageWindow } from "./pagination";
import { RankingsTable } from "./rankings-table";
import { ACTION_CLASSES, StatePanel } from "./state-panel";
import type { Outcome, Position, ValuesResponse } from "./types";
import { ValueExplainer } from "./value-explainer";

const PATHNAME = "/rankings";

const POSITION_NAMES: Record<Position, string> = {
  QB: "quarterbacks",
  RB: "running backs",
  WR: "wide receivers",
  TE: "tight ends",
};

/**
 * Everything below the controls on /rankings, for whichever outcome the API read had.
 * Pure: the page fetches, this renders, so every state can be tested with plain props.
 */
export function RankingsView({
  result,
  position,
  offset,
  pageSize,
  search,
}: {
  result: Outcome<ValuesResponse>;
  position: Position | undefined;
  offset: number;
  pageSize: number;
  search: SearchParams;
}) {
  if (result.kind === "unavailable") {
    return (
      <StatePanel title="Values haven’t been loaded yet">
        <p>
          Rankings are built from player projections, and none have been loaded
          so far. They appear here as soon as the first data load finishes.
        </p>
      </StatePanel>
    );
  }

  if (result.kind === "error") {
    return (
      <StatePanel
        title="Rankings couldn’t load"
        action={
          // A full page load (not a client navigation) so nothing cached in the browser is reused.
          <a href={hrefWith(PATHNAME, search, {})} className={ACTION_CLASSES}>
            Try again
          </a>
        }
      >
        <p>
          The Fantasy Magic data server didn’t answer, so there are no values to
          show right now. Check that it’s running, then try again.
        </p>
      </StatePanel>
    );
  }

  const { data } = result;
  if (data.players.length === 0) {
    return (
      <EmptyRankings position={position} total={data.total} search={search} />
    );
  }

  const format = describeFormat(data.league_format);
  const { first, last } = pageWindow({
    offset,
    count: data.players.length,
    total: data.total,
    pageSize,
  });
  const caption = `${position ? `Ranked ${POSITION_NAMES[position]}` : "Ranked players"} for ${format}, ${first} to ${last} of ${data.total}`;

  return (
    <div className="space-y-6 motion-safe:animate-rise">
      <p className="text-sm text-pretty text-ink-muted">
        <span className="font-semibold text-ink">{format}</span>
        {" · "}Projections from{" "}
        <time dateTime={data.snapshot_date}>
          {formatDate(data.snapshot_date)}
        </time>
        {" · "}Values use projections for weeks {data.from_week}–
        {data.through_week} of the {data.season} season. Bars compare players on
        this page.
      </p>
      <RankingsTable players={data.players} caption={caption} />
      <Pagination
        pathname={PATHNAME}
        search={search}
        offset={offset}
        count={data.players.length}
        total={data.total}
        pageSize={pageSize}
      />
      <div className="pt-6">
        <ValueExplainer />
      </div>
    </div>
  );
}

function EmptyRankings({
  position,
  total,
  search,
}: {
  position: Position | undefined;
  total: number;
  search: SearchParams;
}) {
  if (total > 0) {
    // The URL points past the end of the list (an old link, or a hand-edited offset).
    return (
      <StatePanel
        title="No players on this page"
        action={
          <Link
            href={hrefWith(PATHNAME, search, { offset: null })}
            className={ACTION_CLASSES}
          >
            Go to the first page
          </Link>
        }
      >
        <p>The list ends at player {formatCount(total)}.</p>
      </StatePanel>
    );
  }

  if (position) {
    return (
      <StatePanel
        title={`No ${POSITION_NAMES[position]} ranked yet`}
        action={
          <Link
            href={hrefWith(PATHNAME, search, { position: null, offset: null })}
            className={ACTION_CLASSES}
          >
            Show all positions
          </Link>
        }
      >
        <p>
          The latest projections don’t include any {POSITION_NAMES[position]}.
        </p>
      </StatePanel>
    );
  }

  return (
    <StatePanel title="No players ranked yet">
      <p>
        The latest projections don’t include any quarterbacks, running backs,
        wide receivers, or tight ends.
      </p>
    </StatePanel>
  );
}
