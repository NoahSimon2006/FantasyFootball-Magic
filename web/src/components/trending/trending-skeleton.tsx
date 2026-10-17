function SkeletonTable({ rows }: { rows: number }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-rule bg-card motion-safe:animate-pulse">
      <div className="h-12" />
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 border-t border-rule px-2 py-3 sm:px-4"
        >
          <div className="flex-1 space-y-1.5">
            <div className="h-4 w-36 max-w-full rounded bg-well" />
            <div className="h-3 w-16 rounded bg-well" />
          </div>
          <div className="h-4 w-10 shrink-0 rounded bg-well" />
          <div className="h-6 w-16 shrink-0 rounded-full bg-well" />
        </div>
      ))}
    </div>
  );
}

/** Placeholder sections shaped like /trending, shown while the API answers. */
export function TrendingSkeleton() {
  return (
    <div role="status">
      <span className="sr-only">Loading trending players…</span>
      <div aria-hidden="true" className="space-y-12">
        <div>
          <div className="mb-4 h-7 w-40 rounded bg-well" />
          <SkeletonTable rows={6} />
        </div>
        <div className="grid gap-12 lg:grid-cols-2">
          {[0, 1].map((index) => (
            <div key={index}>
              <div className="mb-4 h-7 w-28 rounded bg-well" />
              <SkeletonTable rows={4} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
