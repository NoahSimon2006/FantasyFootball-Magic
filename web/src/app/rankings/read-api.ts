// Shared by the /rankings and /trending data modules. It lives here because those two pages
// own this folder; move it to src/lib/api/ if a third page needs it.
import type { Outcome } from "@/components/rankings/types";

/** How long a read may take before the page shows its error state instead of loading forever. */
export const API_TIMEOUT_MS = 10_000;

/** The parts of an openapi-fetch result this module looks at. */
interface ApiResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * The `code` from the API's single error shape, `{"error": {"code", "message"}}`. The
 * generated schema only describes 422 bodies, so other statuses are checked at runtime.
 */
export function apiErrorCode(body: unknown): string | undefined {
  if (typeof body !== "object" || body === null || !("error" in body)) {
    return undefined;
  }
  const { error } = body;
  if (typeof error !== "object" || error === null || !("code" in error)) {
    return undefined;
  }
  return typeof error.code === "string" ? error.code : undefined;
}

/**
 * Runs one API call and classifies the answer. Never throws: a refused connection, a
 * timeout, or a body that isn't JSON all become `{ kind: "error" }`, logged with `label`.
 */
export async function readApi<T>(
  label: string,
  call: () => Promise<ApiResult<T>>,
): Promise<Outcome<T>> {
  let result: ApiResult<T>;
  try {
    result = await call();
  } catch (cause) {
    console.error(`${label}: the API could not be reached`, cause);
    return { kind: "error" };
  }

  const { data, error, response } = result;
  if (response.ok && data !== undefined) return { kind: "ok", data };

  const code = apiErrorCode(error);
  if (response.status === 503 && code === "VALUES_UNAVAILABLE") {
    return { kind: "unavailable" };
  }
  console.error(
    `${label}: the API answered ${response.status}${code ? ` ${code}` : ""}`,
  );
  return { kind: "error" };
}
