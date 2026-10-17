import type { Metadata } from "next";
import { Suspense } from "react";

import { FormatPicker } from "@/components/format-picker";
import { ControlsSkeleton } from "@/components/rankings/controls-skeleton";
import type { SearchParams } from "@/components/rankings/href";
import { PositionFilter } from "@/components/rankings/position-filter";
import { RankingsSkeleton } from "@/components/rankings/rankings-skeleton";
import { RankingsView } from "@/components/rankings/rankings-view";
import { PageHeader } from "@/components/ui/page-header";

import { getRankings } from "./data";
import { PAGE_SIZE, parseRankingsQuery } from "./query";

export const metadata: Metadata = {
  title: "Player rankings",
  description:
    "Every redraft player ranked by value for your league format: projected points over a waiver-level replacement.",
};

interface RankingsPageProps {
  searchParams: Promise<SearchParams>;
}

// The heading doesn't depend on the URL, so it's part of the prerendered static shell.
// Everything else reads searchParams, a request-time API, so it sits behind <Suspense>:
// the controls appear as soon as the URL is read, the table once the API answers.
export default function RankingsPage({ searchParams }: RankingsPageProps) {
  return (
    <>
      <PageHeader
        title="Player rankings"
        description="Every player ranked by how many more points he should score this season than a waiver-wire pickup in your league."
      >
        <Suspense fallback={<ControlsSkeleton pills={5} />}>
          <RankingsControls searchParams={searchParams} />
        </Suspense>
      </PageHeader>
      <Suspense fallback={<RankingsSkeleton />}>
        <RankingsResults searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function RankingsControls({ searchParams }: RankingsPageProps) {
  const search = await searchParams;
  const query = parseRankingsQuery(search);
  return (
    <div className="flex flex-col gap-4">
      <FormatPicker format={query.format} />
      <PositionFilter search={search} current={query.position} />
    </div>
  );
}

async function RankingsResults({ searchParams }: RankingsPageProps) {
  const search = await searchParams;
  const query = parseRankingsQuery(search);
  return (
    <RankingsView
      result={await getRankings(query)}
      position={query.position}
      offset={query.offset}
      pageSize={PAGE_SIZE}
      search={search}
    />
  );
}
