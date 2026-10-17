import { StarMark } from "@/components/ui/star-mark";

import type { EvaluationProblem } from "./evaluate-trade";
import type { PlayerRef, TradePicks } from "./trade-rules";

interface ProblemCopy {
  title: string;
  body: string;
  /** Whether trying the same trade again can help (vs. the trade itself needing a change). */
  retry: boolean;
}

const LIST = new Intl.ListFormat("en-US", {
  style: "long",
  type: "conjunction",
});

/** The picked players whose ids the API's not-found message names. */
function playersNamedIn(message: string, picks: TradePicks): PlayerRef[] {
  // Whole tokens, so id "40" doesn't match inside "4046".
  const tokens = new Set(message.split(/[^\w]+/));
  return [...picks.a, ...picks.b].filter((player) =>
    tokens.has(player.player_id),
  );
}

export function describeProblem(
  problem: EvaluationProblem,
  picks: TradePicks,
): ProblemCopy {
  switch (problem.kind) {
    case "values-unavailable":
      return {
        title: "Values aren't loaded yet",
        body: "There are no projections to value players with until the first data load runs. Your trade stays here; evaluate it again once values are in.",
        retry: true,
      };
    case "player-not-found": {
      const names = playersNamedIn(problem.message, picks).map((p) => p.name);
      return {
        title:
          names.length === 1
            ? `${names[0]} can't be valued yet`
            : "Some players can't be valued yet",
        body:
          names.length === 0
            ? "One of these players isn't in the latest value snapshot. Remove recently added players and evaluate again."
            : `${LIST.format(names)} ${names.length === 1 ? "isn't" : "aren't"} in the latest value snapshot, so the trade can't be scored. Remove ${names.length === 1 ? "that player" : "those players"} and evaluate again.`,
        retry: false,
      };
    }
    case "rejected":
      return {
        title: "This trade can't be evaluated",
        body: `The API turned it down: ${problem.message}`,
        retry: false,
      };
    case "server":
      return {
        title: "The evaluation failed",
        body: `The API hit an error (${problem.message}). Try again in a moment.`,
        retry: true,
      };
    case "unreachable":
      return {
        title: "Can't reach the API",
        body: "The request got no answer. Fantasy Magic runs locally for now, so check that the API server is running, then try again.",
        retry: true,
      };
  }
}

/**
 * Why there's no verdict. "Values aren't loaded yet" is an expected state before the first
 * data load, so it is announced politely and styled calmly; the rest are errors (alerts).
 */
export function EvaluationProblemPanel({
  problem,
  picks,
  onRetry,
}: {
  problem: EvaluationProblem;
  picks: TradePicks;
  onRetry: () => void;
}) {
  const copy = describeProblem(problem, picks);
  const expected = problem.kind === "values-unavailable";

  return (
    <div
      role={expected ? "status" : "alert"}
      className={`rounded-3xl border p-6 sm:p-8 ${expected ? "border-violet/30 bg-violet-soft" : "border-negative/30 bg-negative-soft"}`}
    >
      <h2 className="flex items-center gap-2.5 font-display text-2xl font-semibold tracking-tight">
        {expected ? (
          <StarMark className="size-5 text-violet" />
        ) : (
          <svg
            viewBox="0 0 20 20"
            aria-hidden="true"
            className="size-5 text-negative"
          >
            <path
              fill="currentColor"
              d="M10 1.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17Zm-.9 4.2h1.8l-.2 5.6H9.3l-.2-5.6Zm.9 9.1a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Z"
            />
          </svg>
        )}
        {copy.title}
      </h2>
      <p className="mt-2 max-w-prose text-ink-muted">{copy.body}</p>
      {copy.retry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex h-10 items-center rounded-full border border-rule-strong bg-card px-5 text-sm font-semibold text-ink transition-colors hover:border-gold"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
