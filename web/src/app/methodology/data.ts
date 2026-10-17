import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Methodology = components["schemas"]["MethodologyResponse"];

/** Either the live numbers, or a reason the page must explain their absence. */
export type MethodologyResult =
  { kind: "ok"; data: Methodology } | { kind: "error" };

/**
 * The value model's real parameters and data counts, read from the API at request time.
 * Never throws: an unreachable API becomes `{ kind: "error" }`, so the page still explains
 * the method and only the live card says the numbers are unavailable.
 */
export async function getMethodology(): Promise<MethodologyResult> {
  try {
    const { data } = await api.GET("/api/v1/methodology");
    return data ? { kind: "ok", data } : { kind: "error" };
  } catch {
    // fetch() rejects when the API isn't running at all; that's a state, not a crash.
    return { kind: "error" };
  }
}
