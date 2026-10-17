import Link from "next/link";

import { formatCount } from "./format";
import { hrefWith, type SearchParams } from "./href";

const LINK_CLASSES =
  "inline-flex h-10 items-center gap-1.5 rounded-full border border-rule-strong bg-card px-4 text-sm font-semibold text-ink hover:bg-well";

/** Which slice of the list a page shows, and where its neighbours start. */
export function pageWindow({
  offset,
  count,
  total,
  pageSize,
}: {
  offset: number;
  count: number;
  total: number;
  pageSize: number;
}) {
  return {
    first: offset + 1,
    last: offset + count,
    previousOffset: offset > 0 ? Math.max(0, offset - pageSize) : null,
    nextOffset: offset + count < total ? offset + pageSize : null,
  };
}

/**
 * Previous / next as plain links (each page has its own URL), with "Showing 51–100 of 312"
 * between them. A link that would lead nowhere is left out rather than shown disabled.
 */
export function Pagination({
  pathname,
  search,
  offset,
  count,
  total,
  pageSize,
}: {
  pathname: string;
  search: SearchParams;
  offset: number;
  count: number;
  total: number;
  pageSize: number;
}) {
  const { first, last, previousOffset, nextOffset } = pageWindow({
    offset,
    count,
    total,
    pageSize,
  });
  const offsetHref = (target: number) =>
    hrefWith(pathname, search, {
      offset: target === 0 ? null : String(target),
    });

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-3"
    >
      <div className="min-w-24">
        {previousOffset !== null ? (
          <Link
            href={offsetHref(previousOffset)}
            aria-label="Previous page"
            className={LINK_CLASSES}
          >
            <span aria-hidden="true">←</span>
            Previous
          </Link>
        ) : null}
      </div>
      <p className="text-sm text-ink-muted">
        Showing {formatCount(first)}–{formatCount(last)} of {formatCount(total)}
      </p>
      <div className="flex min-w-24 justify-end">
        {nextOffset !== null ? (
          <Link
            href={offsetHref(nextOffset)}
            aria-label="Next page"
            className={LINK_CLASSES}
          >
            Next
            <span aria-hidden="true">→</span>
          </Link>
        ) : null}
      </div>
    </nav>
  );
}
