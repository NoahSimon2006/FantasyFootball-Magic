import type { ApiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { formatToQuery, type LeagueFormatParams } from "@/lib/league-format";

import type { TradePicks } from "./trade-rules";

export type TradeEvaluation = components["schemas"]["TradeEvaluationResponse"];

/** Every way an evaluation can fail, as the UI needs to tell them apart. */
export type EvaluationProblem =
  /** 503 VALUES_UNAVAILABLE: no projections ingested yet, so nothing has a value. */
  | { kind: "values-unavailable" }
  /** 404 PLAYER_NOT_FOUND: a picked player isn't in the current value snapshot. */
  | { kind: "player-not-found"; message: string }
  /** Any other 4xx in the API's error shape (e.g. 422 VALIDATION_ERROR). */
  | { kind: "rejected"; message: string }
  /** A 5xx in the API's error shape: the API answered, but failed. */
  | { kind: "server"; message: string }
  /** No usable answer: network failure, timeout, or a proxy error page while the API is down. */
  | { kind: "unreachable" };

export type EvaluationOutcome =
  | { ok: true; evaluation: TradeEvaluation }
  | { ok: false; problem: EvaluationProblem };

/** Past this, a request is reported as unreachable instead of spinning forever. */
const EVALUATE_TIMEOUT_MS = 15_000;

/**
 * The caller's signal plus a timeout. AbortSignal.any is recent (Safari 17.4, Chrome 116);
 * where it's missing, keep just the caller's signal rather than fail every evaluation.
 */
function withTimeout(signal: AbortSignal, ms: number): AbortSignal {
  if (
    typeof AbortSignal.any !== "function" ||
    typeof AbortSignal.timeout !== "function"
  ) {
    return signal;
  }
  return AbortSignal.any([signal, AbortSignal.timeout(ms)]);
}

/**
 * Reads the API's single error shape, `{"error": {"code", "message"}}`. Checked at runtime
 * because the OpenAPI schema only declares 422 bodies (and in FastAPI's default shape).
 */
export function readApiError(
  body: unknown,
): { code: string; message: string } | null {
  if (typeof body !== "object" || body === null || !("error" in body)) {
    return null;
  }
  const { error } = body;
  if (
    typeof error !== "object" ||
    error === null ||
    !("code" in error) ||
    !("message" in error)
  ) {
    return null;
  }
  const { code, message } = error;
  return typeof code === "string" && typeof message === "string"
    ? { code, message }
    : null;
}

function classify(status: number, body: unknown): EvaluationProblem {
  const apiError = readApiError(body);
  if (apiError === null) return { kind: "unreachable" };
  if (apiError.code === "VALUES_UNAVAILABLE") {
    return { kind: "values-unavailable" };
  }
  if (apiError.code === "PLAYER_NOT_FOUND") {
    return { kind: "player-not-found", message: apiError.message };
  }
  return status >= 500
    ? { kind: "server", message: apiError.message }
    : { kind: "rejected", message: apiError.message };
}

/**
 * POST /api/v1/trades/evaluate for the picked players in `format`. Never throws: every
 * failure comes back as a typed problem. `signal` lets the caller cancel a superseded call.
 */
export async function evaluateTrade(
  client: ApiClient,
  picks: TradePicks,
  format: LeagueFormatParams,
  signal: AbortSignal,
): Promise<EvaluationOutcome> {
  try {
    const { data, error, response } = await client.POST(
      "/api/v1/trades/evaluate",
      {
        body: {
          receives_a: picks.a.map((player) => player.player_id),
          receives_b: picks.b.map((player) => player.player_id),
          ...formatToQuery(format),
        },
        signal: withTimeout(signal, EVALUATE_TIMEOUT_MS),
      },
    );
    if (data !== undefined) return { ok: true, evaluation: data };
    return { ok: false, problem: classify(response.status, error) };
  } catch {
    // fetch rejects on network failure and on abort; both mean "no answer".
    return { ok: false, problem: { kind: "unreachable" } };
  }
}
