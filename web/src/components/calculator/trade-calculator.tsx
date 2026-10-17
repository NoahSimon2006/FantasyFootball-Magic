"use client";

import { useRef, useState } from "react";

import { StarMark } from "@/components/ui/star-mark";
import { browserApi, type ApiClient } from "@/lib/api/client";
import { describeFormat, type LeagueFormatParams } from "@/lib/league-format";

import {
  evaluateTrade,
  type EvaluationProblem,
  type TradeEvaluation,
} from "./evaluate-trade";
import { EvaluationProblemPanel } from "./evaluation-problem";
import { PlayerPicker } from "./player-picker";
import { TradeResult, verdictSummary } from "./trade-result";
import {
  TEAM_NAME,
  type PlayerRef,
  type TradePicks,
  type TradeSide,
} from "./trade-rules";

/** Each state remembers the `key` (trade + format) it was computed for. */
type EvaluationState =
  | { status: "idle" }
  | { status: "loading"; key: string; previous: TradeEvaluation | null }
  | { status: "done"; key: string; evaluation: TradeEvaluation }
  | { status: "failed"; key: string; problem: EvaluationProblem };

/** What a verdict depends on. When it changes, the verdict on screen is out of date. */
function tradeKey(picks: TradePicks, format: LeagueFormatParams): string {
  return JSON.stringify([
    picks.a.map((player) => player.player_id),
    picks.b.map((player) => player.player_id),
    format.teams,
    format.ppr,
    format.superflex,
  ]);
}

function lastVerdict(state: EvaluationState): TradeEvaluation | null {
  if (state.status === "done") return state.evaluation;
  if (state.status === "loading") return state.previous;
  return null;
}

/**
 * The trade calculator: two sides, an Evaluate button, and the verdict.
 *
 * Why a button instead of evaluating automatically after every change: trades get built one
 * player at a time, and an automatic verdict would flip back and forth on half-built trades
 * while firing a request per change. One press is one request, the verdict never shifts
 * under the reader, and there's no effect-driven fetching or response racing to reason
 * about. If the trade or the league format changes after a verdict, the verdict stays on
 * screen, dimmed and marked out of date, until the next evaluation.
 */
export function TradeCalculator({
  format,
  client = browserApi,
}: {
  format: LeagueFormatParams;
  /** The API client; tests pass one with a fake fetch. */
  client?: ApiClient;
}) {
  const [picks, setPicks] = useState<TradePicks>({ a: [], b: [] });
  const [state, setState] = useState<EvaluationState>({ status: "idle" });
  const inFlight = useRef<AbortController | null>(null);

  const key = tradeKey(picks, format);
  const isCurrent = state.status !== "idle" && state.key === key;
  const loading = state.status === "loading";
  const missing = (["a", "b"] as const).filter(
    (side) => picks[side].length === 0,
  );
  const ready = missing.length === 0;

  function add(side: TradeSide, player: PlayerRef) {
    setPicks((current) => ({ ...current, [side]: [...current[side], player] }));
  }

  function remove(side: TradeSide, playerId: string) {
    setPicks((current) => ({
      ...current,
      [side]: current[side].filter((player) => player.player_id !== playerId),
    }));
  }

  function clear() {
    inFlight.current?.abort();
    setPicks({ a: [], b: [] });
    setState({ status: "idle" });
  }

  async function evaluate() {
    // A newer press (or Clear) supersedes any request still running.
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    const requestKey = key;
    setState((current) => ({
      status: "loading",
      key: requestKey,
      previous: lastVerdict(current),
    }));

    const outcome = await evaluateTrade(
      client,
      picks,
      format,
      controller.signal,
    );
    if (controller.signal.aborted) return;
    setState(
      outcome.ok
        ? { status: "done", key: requestKey, evaluation: outcome.evaluation }
        : { status: "failed", key: requestKey, problem: outcome.problem },
    );
  }

  let hint: string;
  if (!ready) {
    hint =
      missing.length === 2
        ? "Add at least one player to each side."
        : `Add at least one player to ${TEAM_NAME[missing[0] ?? "a"]}.`;
  } else {
    hint = `Values for ${describeFormat(format)}.`;
  }

  let announcement = "";
  if (state.status === "loading") announcement = "Evaluating the trade…";
  else if (state.status === "done" && isCurrent) {
    announcement = verdictSummary(state.evaluation);
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 md:gap-6">
        {(["a", "b"] as const).map((side) => (
          <PlayerPicker
            key={side}
            side={side}
            picks={picks}
            onAdd={(player) => add(side, player)}
            onRemove={(playerId) => remove(side, playerId)}
            client={client}
          />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <button
          type="button"
          onClick={() => void evaluate()}
          // Stays enabled while loading: disabling a focused button can drop keyboard focus
          // to <body>, and a second press just restarts the request (evaluate() aborts).
          disabled={!ready}
          className="inline-flex h-12 items-center gap-2 rounded-full bg-gold px-7 font-semibold text-on-gold shadow-sm transition-[filter] hover:brightness-110 disabled:cursor-not-allowed disabled:bg-well disabled:text-ink-faint disabled:shadow-none disabled:hover:brightness-100"
        >
          {loading ? (
            <>
              <span
                aria-hidden="true"
                className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
              />
              Evaluating…
            </>
          ) : (
            "Evaluate trade"
          )}
        </button>
        {picks.a.length + picks.b.length > 0 ? (
          <button
            type="button"
            onClick={clear}
            className="h-10 rounded-full px-3 text-sm font-medium text-ink-muted underline-offset-4 hover:text-ink hover:underline"
          >
            Clear trade
          </button>
        ) : null}
        <p className="text-sm text-ink-muted">{hint}</p>
      </div>

      <section aria-label="Result" aria-busy={loading}>
        <ResultArea
          state={state}
          isCurrent={isCurrent}
          picks={picks}
          onRetry={() => void evaluate()}
        />
      </section>

      <p role="status" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}

function ResultArea({
  state,
  isCurrent,
  picks,
  onRetry,
}: {
  state: EvaluationState;
  isCurrent: boolean;
  picks: TradePicks;
  onRetry: () => void;
}) {
  switch (state.status) {
    case "loading":
      return state.previous !== null ? (
        <TradeResult evaluation={state.previous} stale />
      ) : (
        <div className="grid min-h-56 place-items-center rounded-3xl border border-rule bg-card p-8 text-ink-muted">
          <p className="flex items-center gap-3">
            <StarMark className="size-5 animate-pulse text-gold" />
            Weighing the trade…
          </p>
        </div>
      );
    case "done":
      return (
        <div className="space-y-3">
          {!isCurrent ? (
            <p className="rounded-xl border border-gold/40 bg-gold-soft px-4 py-3 text-sm text-ink">
              The trade or league format has changed since this verdict.
              Evaluate again to update it.
            </p>
          ) : null}
          <TradeResult evaluation={state.evaluation} stale={!isCurrent} />
        </div>
      );
    case "failed":
      // A problem only applies to the trade it came from; once that changes, start fresh.
      return isCurrent ? (
        <EvaluationProblemPanel
          problem={state.problem}
          picks={picks}
          onRetry={onRetry}
        />
      ) : (
        <EmptyResult />
      );
    case "idle":
      return <EmptyResult />;
  }
}

function EmptyResult() {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-rule-strong/60 p-8 text-center">
      <StarMark className="size-6 text-gold" />
      <p className="max-w-md text-ink-muted">
        Add players to both sides, then evaluate. You&apos;ll see who receives
        more value, by how much, and every reason behind the verdict.
      </p>
    </div>
  );
}
