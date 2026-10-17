// Names for the generated API types this feature uses. These are aliases, not copies: the
// shapes come from schema.d.ts, so a backend change shows up here as a type error.
import type { components, operations } from "@/lib/api/schema";

export type ValuesResponse = components["schemas"]["ValuesResponse"];
export type PlayerValue = components["schemas"]["PlayerValueOut"];

type ValuesQuery = NonNullable<
  operations["list_values_api_v1_values_get"]["parameters"]["query"]
>;

/** A position the values endpoint can filter by, taken from the API schema. */
export type Position = NonNullable<ValuesQuery["position"]>;

/** Filter options in display order; `satisfies` rejects anything the API wouldn't accept. */
export const POSITIONS = [
  "QB",
  "RB",
  "WR",
  "TE",
] as const satisfies readonly Position[];

/**
 * What a page can show for one API read (shared with /trending). Each kind is a designed
 * state, so a view switches on `kind` instead of catching exceptions.
 */
export type Outcome<T> =
  | { kind: "ok"; data: T }
  /** 503 VALUES_UNAVAILABLE: no projections loaded yet, the normal state before the first data load. */
  | { kind: "unavailable" }
  /** The API was unreachable, timed out, or answered with something unusable. */
  | { kind: "error" };
