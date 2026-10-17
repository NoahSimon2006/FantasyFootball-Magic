/**
 * Holds the place of the format picker and a row of filter pills until the URL is read
 * (shared with /trending), so the controls don't push the page down when they appear.
 */
export function ControlsSkeleton({ pills }: { pills: number }) {
  return (
    <div aria-hidden="true" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        {[0, 1].map((index) => (
          <div key={index} className="w-36">
            <div className="mb-1 h-4 w-20 rounded bg-well" />
            <div className="h-10 rounded-lg border border-rule bg-card" />
          </div>
        ))}
        <div className="h-10 w-28 rounded-lg bg-well" />
      </div>
      <div>
        <div className="mb-1 h-4 w-16 rounded bg-well" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: pills }, (_, index) => (
            <div key={index} className="h-9 w-14 rounded-full bg-well" />
          ))}
        </div>
      </div>
    </div>
  );
}
