import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/ui/page-header";

import { getMethodology } from "./data";
import { LiveNumbers } from "./live-numbers";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How Fantasy Magic computes player values and trade verdicts, and its limits.",
};

/**
 * The method in words (static, part of the prerendered shell) plus a card of live numbers.
 * The numbers are fetched at request time inside <Suspense> rather than cached with
 * 'use cache': a cached read would run during `next build`, which must work with the API
 * offline, and these counts change every time data is loaded.
 */
export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-3xl pb-16">
      <PageHeader
        title="How the values work"
        description="Everything the model does, in plain English, including what it can't do yet."
      />

      <section aria-labelledby="live" className="mb-12">
        <h2 id="live" className="sr-only">
          Live numbers
        </h2>
        <Suspense
          fallback={
            <p role="status" className="text-ink-muted">
              Loading the live numbers…
            </p>
          }
        >
          <LiveNumbersFromApi />
        </Suspense>
      </section>

      <div className="space-y-10 text-lg leading-relaxed text-pretty">
        <Section title="What a value means">
          <p>
            A player&apos;s value is how many more fantasy points he is
            projected to score from this week to the end of the fantasy season
            than a <em>replacement-level</em> player at his position: the best
            one you could pick up for free. Values depend on your league&apos;s
            format (number of teams, points per reception, and superflex), so
            the same player has a different value in different leagues.
          </p>
        </Section>

        <Section title="How replacement level is found">
          <p>
            The model fills every team&apos;s starting lineup from one shared
            pool of players: single-position slots first (QB, RB, WR, TE), then
            flex slots with the best players left over, then superflex. Whoever
            is left is replacement level. This is why superflex raises
            quarterback values: the extra slot uses up more quarterbacks, so the
            best one left over is worse, and every starter&apos;s edge over him
            grows.
          </p>
        </Section>

        <Section title="How a trade is judged">
          <p>
            Each side&apos;s players are added up, with a discount for extra
            pieces: two decent players compete for the lineup spots that one
            star fills, and the team receiving more players has to cut someone
            to make room. When the gap is small, the verdict says it&apos;s too
            close to call instead of naming a winner. Every adjustment is shown
            next to the verdict as its own reason, never folded silently into a
            total.
          </p>
        </Section>

        <Section title="Where the data comes from">
          <p>
            Everything comes from Sleeper&apos;s public API. The NFL player list
            is refreshed at most once a day. Weekly projections are saved as a
            dated snapshot each time they are loaded, which is what lets the
            trending page compare this week with last week. Trades come from
            public redraft leagues found by a crawler that starts from a few
            usernames and follows league members outward, stores only Sleeper
            ids and league settings (never names), and stays well under
            Sleeper&apos;s rate limit.
          </p>
        </Section>

        <Section title="What this version can't do yet">
          <ul className="list-disc space-y-2 pl-6">
            <li>
              Values come from projections only. The trades being collected are
              not used to set prices yet, so these are &ldquo;what the
              projections say&rdquo;, not &ldquo;what managers actually
              pay&rdquo;.
            </li>
            <li>
              In superflex, real trade markets usually value top quarterbacks
              more than this model does, because a second starting quarterback
              is so hard to find.
            </li>
            <li>Kickers and defenses aren&apos;t valued.</li>
            <li>
              The discount for extra players is a hand-picked starting point,
              not yet measured from real trades.
            </li>
          </ul>
        </Section>

        <Section title="What comes next">
          <p>
            The next version learns values from the real trades the crawler
            collects, shows the evidence behind every value (how many trades,
            how recent, how uncertain), and is checked every week against this
            projection-only version. The results of those checks will be
            published on this page.
          </p>
        </Section>
      </div>
    </div>
  );
}

async function LiveNumbersFromApi() {
  return <LiveNumbers result={await getMethodology()} />;
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="font-display text-2xl font-semibold tracking-tight">
        {title}
      </h2>
      <div className="mt-3 text-ink-muted">{children}</div>
    </section>
  );
}
