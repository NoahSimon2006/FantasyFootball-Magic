import type { Metadata } from "next";
import { Suspense } from "react";

import { CalculatorSkeleton } from "@/components/calculator/calculator-skeleton";
import { TradeCalculator } from "@/components/calculator/trade-calculator";
import { FormatPicker } from "@/components/format-picker";
import { PageHeader } from "@/components/ui/page-header";
import { parseFormatParams } from "@/lib/league-format";

export const metadata: Metadata = {
  title: "Trade calculator",
  description:
    "See who wins a fantasy football trade, by how much, and why, in your league's format.",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default function CalculatorPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  return (
    <>
      <PageHeader
        title="Trade calculator"
        description="Add what each team receives, then evaluate. Values are worked out for the league format you pick."
      />
      {/* searchParams is request-time data under cacheComponents, so the part that reads
          it streams in behind this boundary; the header above is in the prerendered shell.
          Nothing here calls the API on the server: the browser does, after hydration. */}
      <Suspense fallback={<CalculatorSkeleton />}>
        <CalculatorForUrl searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function CalculatorForUrl({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  // The format lives in the URL (?teams=10&ppr=0.5&superflex=true) so links are shareable.
  const format = parseFormatParams(await searchParams);
  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-rule bg-card/70 px-4 py-3 sm:px-5">
        <FormatPicker format={format} />
      </div>
      <TradeCalculator format={format} />
    </div>
  );
}
