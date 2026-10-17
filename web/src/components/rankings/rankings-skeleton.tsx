/** Placeholder rows shaped like the rankings table, shown while the API answers. */
export function RankingsSkeleton() {
  return (
    <div role="status">
      <span className="sr-only">Loading rankings…</span>
      <div aria-hidden="true">
        <div className="mb-4 h-5 w-72 max-w-full rounded bg-well" />
        <div className="overflow-hidden rounded-2xl border border-rule bg-card motion-safe:animate-pulse">
          <div className="h-12" />
          {Array.from({ length: 10 }, (_, index) => (
            <div
              key={index}
              className="flex items-center gap-4 border-t border-rule px-2 py-3 sm:px-4"
            >
              <div className="h-4 w-8 shrink-0 rounded bg-well" />
              <div className="flex-1 space-y-1.5">
                <div className="h-4 w-40 max-w-full rounded bg-well" />
                <div className="h-3 w-16 rounded bg-well" />
              </div>
              <div className="h-4 w-12 shrink-0 rounded bg-well" />
              <div className="h-2 w-20 shrink-0 rounded-full bg-well sm:w-40" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
