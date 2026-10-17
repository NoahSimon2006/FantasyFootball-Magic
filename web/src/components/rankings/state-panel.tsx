import type { ReactNode } from "react";

/** Gold pill for the one action a state panel offers (a link or a button). */
export const ACTION_CLASSES =
  "inline-flex h-10 items-center rounded-full bg-gold px-5 text-sm font-semibold text-on-gold hover:brightness-105";

/**
 * Stands in for a data view that has nothing to show: data not loaded yet, a failed load,
 * or an empty page (shared with /trending). The title says what happened; the body says
 * why and what to do next.
 */
export function StatePanel({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-rule bg-card px-5 py-7 sm:px-8 sm:py-9">
      <h2 className="font-display text-2xl font-semibold text-balance text-ink">
        {title}
      </h2>
      <div className="mt-3 max-w-prose space-y-2 text-pretty text-ink-muted">
        {children}
      </div>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
