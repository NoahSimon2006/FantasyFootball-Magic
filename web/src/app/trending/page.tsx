import type { Metadata } from "next";
import { Suspense } from "react";

import { FormatPicker } from "@/components/format-picker";
import { ControlsSkeleton } from "@/components/rankings/controls-skeleton";
import type { SearchParams } from "@/components/rankings/href";
import { TrendingSkeleton } from "@/components/trending/trending-skeleton";
import { TrendingView } from "@/components/trending/trending-view";
import { WindowSelector } from "@/components/trending/window-selector";
import { PageHeader } from "@/components/ui/page-header";

import { getTrending } from "./data";
import { parseTrendingQuery } from "./query";

export const metadata: Metadata = {
  title: "Trending players",
  description:
    "The most-traded players in redraft leagues, and whose value is rising or falling.",
};

interface TrendingPageProps {
  searchParams: Promise<SearchParams>;
}

// Same shape as /rankings: the heading is in the static shell, and everything that reads
// searchParams (a request-time API) streams in behind its own <Suspense> boundary.
export default function TrendingPage({ searchParams }: TrendingPageProps) {
  return (
    <>
      <PageHeader
        title="Trending players"
        description="Who redraft managers are trading, and whose value is moving."
      >
        <Suspense fallback={<ControlsSkeleton pills={2} />}>
          <TrendingControls searchParams={searchParams} />
        </Suspense>
      </PageHeader>
      <Suspense fallback={<TrendingSkeleton />}>
        <TrendingResults searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function TrendingControls({ searchParams }: TrendingPageProps) {
  const search = await searchParams;
  const query = parseTrendingQuery(search);
  return (
    <div className="flex flex-col gap-4">
      <FormatPicker format={query.format} />
      <WindowSelector search={search} current={query.days} />
    </div>
  );
}

async function TrendingResults({ searchParams }: TrendingPageProps) {
  const search = await searchParams;
  const query = parseTrendingQuery(search);
  return (
    <TrendingView
      result={await getTrending(query)}
      days={query.days}
      search={search}
    />
  );
}
