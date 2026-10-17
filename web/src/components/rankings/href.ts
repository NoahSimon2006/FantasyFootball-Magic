// Shared by /rankings and /trending. It lives here because those two pages own this folder;
// move it to src/lib/ if a third page needs it.

/** A page's query params as Next.js passes them: a repeated key arrives as an array. */
export type SearchParams = Record<string, string | string[] | undefined>;

/**
 * A link to `pathname` that keeps every current query param except those in `changes`,
 * where a string sets the param and `null` removes it. Filters and pagination build their
 * links with this, so a click changes exactly one thing and the league format stays put.
 */
export function hrefWith(
  pathname: string,
  search: SearchParams,
  changes: Record<string, string | null>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(search)) {
    if (key in changes || value === undefined) continue;
    for (const item of Array.isArray(value) ? value : [value]) {
      params.append(key, item);
    }
  }
  for (const [key, value] of Object.entries(changes)) {
    if (value !== null) params.set(key, value);
  }
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}
