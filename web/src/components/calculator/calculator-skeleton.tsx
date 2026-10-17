import { TEAM_NAME } from "./trade-rules";

/**
 * The calculator's shape while the page reads the league format from the URL. It ships in
 * the prerendered shell, so it mirrors the real layout to keep anything from jumping.
 */
export function CalculatorSkeleton() {
  return (
    <div aria-busy="true" className="space-y-8">
      <p role="status" className="sr-only">
        Loading the calculator…
      </p>
      <div className="h-[4.5rem] animate-pulse rounded-2xl border border-rule bg-card/70" />
      <div className="grid gap-4 md:grid-cols-2 md:gap-6">
        {(["a", "b"] as const).map((side) => (
          <div
            key={side}
            className="rounded-2xl border border-rule bg-card p-5 sm:p-6"
          >
            <p className="font-display text-2xl font-semibold tracking-tight text-ink-muted">
              {TEAM_NAME[side]} receives
            </p>
            <div className="mt-11 h-11 animate-pulse rounded-lg bg-well" />
            <div className="mt-9 h-16 rounded-xl border border-dashed border-rule" />
          </div>
        ))}
      </div>
    </div>
  );
}
