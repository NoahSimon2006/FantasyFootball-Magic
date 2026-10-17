import type { ReactNode } from "react";

import { formatDate } from "@/components/rankings/format";
import { hrefWith, type SearchParams } from "@/components/rankings/href";
import { ACTION_CLASSES, StatePanel } from "@/components/rankings/state-panel";
import type { Outcome } from "@/components/rankings/types";

import { HistoryNotice } from "./history-notice";
import { MostTradedTable } from "./most-traded-table";
import { MoversTable } from "./movers-table";
import type { TrendingData } from "./types";

/**
 * Everything below the controls on /trending, for whichever outcome the API read had.
 * Pure: the page fetches, this renders, so every state can be tested with plain props.
 */
export function TrendingView({
  result,
  days,
  search,
}: {
  result: Outcome<TrendingData>;
  days: number;
  search: SearchParams;
}) {
  if (result.kind === "unavailable") {
    return (
      <StatePanel title="Trending isn’t available yet">
        <p>
          Trending is built from player values and trades, and the values
          haven’t been loaded so far. This page fills in once the first data
          load finishes.
        </p>
      </StatePanel>
    );
  }

  if (result.kind === "error") {
    return (
      <StatePanel
        title="Trending couldn’t load"
        action={
          // A full page load (not a client navigation) so nothing cached in the browser is reused.
          <a
            href={hrefWith("/trending", search, {})}
            className={ACTION_CLASSES}
          >
            Try again
          </a>
        }
      >
        <p>
          The Fantasy Magic data server didn’t answer, so there’s nothing to
          show right now. Check that it’s running, then try again.
        </p>
      </StatePanel>
    );
  }

  const { trending, history } = result.data;

  return (
    <div className="space-y-12 motion-safe:animate-rise">
      <section aria-labelledby="most-traded-title">
        <SectionHeading id="most-traded-title" title="Most traded">
          How many redraft trades each player was part of in the last {days}{" "}
          days, next to the {days} days before.
        </SectionHeading>
        {trending.most_traded.length > 0 ? (
          <MostTradedTable players={trending.most_traded} days={days} />
        ) : (
          <EmptyNote>
            No redraft trades recorded in the last {days} days yet.
          </EmptyNote>
        )}
      </section>

      {history.kind === "ready" ? (
        <div className="space-y-6">
          <p className="text-sm text-ink-muted">
            Value changes since{" "}
            <time dateTime={history.comparedTo}>
              {formatDate(history.comparedTo)}
            </time>
            , using projections from{" "}
            <time dateTime={history.snapshotDate}>
              {formatDate(history.snapshotDate)}
            </time>
            .
          </p>
          <div className="grid gap-12 lg:grid-cols-2">
            <section aria-labelledby="risers-title">
              <SectionHeading id="risers-title" title="Risers">
                Biggest gains in value.
              </SectionHeading>
              {trending.risers.length > 0 ? (
                <MoversTable
                  moves={trending.risers}
                  caption={`Risers: biggest value gains over ${days} days`}
                />
              ) : (
                <EmptyNote>No player gained value over this window.</EmptyNote>
              )}
            </section>
            <section aria-labelledby="fallers-title">
              <SectionHeading id="fallers-title" title="Fallers">
                Biggest drops in value.
              </SectionHeading>
              {trending.fallers.length > 0 ? (
                <MoversTable
                  moves={trending.fallers}
                  caption={`Fallers: biggest value drops over ${days} days`}
                />
              ) : (
                <EmptyNote>No player lost value over this window.</EmptyNote>
              )}
            </section>
          </div>
        </div>
      ) : (
        <HistoryNotice history={history} days={days} />
      )}

      <p className="text-xs text-ink-muted">
        Trades come from public Sleeper leagues; projections come from Sleeper.
      </p>
    </div>
  );
}

function SectionHeading({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="mb-4">
      <h2 id={id} className="font-display text-2xl font-semibold text-ink">
        {title}
      </h2>
      <p className="mt-1 text-sm text-pretty text-ink-muted">{children}</p>
    </div>
  );
}

function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl border border-dashed border-rule-strong px-5 py-6 text-ink-muted">
      {children}
    </p>
  );
}
