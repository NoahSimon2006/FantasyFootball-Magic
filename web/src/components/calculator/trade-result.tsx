import Link from "next/link";
import { useId } from "react";

import { Chip } from "@/components/ui/chip";
import { StarMark } from "@/components/ui/star-mark";
import { describeFormat } from "@/lib/league-format";

import type { TradeEvaluation } from "./evaluate-trade";
import {
  formatPercent,
  formatPoints,
  formatSnapshotDate,
} from "./number-format";
import { SIDE_DOT, TEAM_NAME, type TradeSide } from "./trade-rules";

type Verdict = TradeEvaluation["verdict"];
type Driver = TradeEvaluation["drivers"][number];
type SideValues = TradeEvaluation["side_a"];

const HEADLINE: Record<Verdict, string> = {
  a: "Team A wins",
  b: "Team B wins",
  even: "Too close to call",
};

// The margin numeral takes the winner's colour; the headline above it names the winner.
const MARGIN_COLOUR: Record<Verdict, string> = {
  a: "text-gold-ink",
  b: "text-violet",
  even: "text-ink",
};

/**
 * Each valuation method in plain English. Keyed by the schema's `method` type, so a new
 * method from the API fails the type check until it is described here.
 */
const METHOD_DESCRIPTION: Record<TradeEvaluation["method"], string> = {
  projection_vor_v0:
    "Values come from model v0: each player's projected rest-of-season fantasy points above a replacement-level player in this league format. It uses projections only, with no evidence from real trades yet.",
};

/** One sentence for screen readers when a verdict arrives. */
export function verdictSummary(evaluation: TradeEvaluation): string {
  const margin = formatPoints(evaluation.margin);
  return evaluation.verdict === "even"
    ? `Too close to call: the sides are ${margin} value points apart.`
    : `${HEADLINE[evaluation.verdict]} by ${margin} value points.`;
}

/**
 * A trade verdict: who wins and by how much, each side's share of the value, the reasons
 * (drivers), each player's numbers, and how the values were made. `stale` dims it when the
 * trade has changed since it was computed.
 */
export function TradeResult({
  evaluation,
  stale = false,
}: {
  evaluation: TradeEvaluation;
  stale?: boolean;
}) {
  const headingId = useId();
  const { verdict, margin, margin_share: marginShare } = evaluation;

  return (
    <article
      aria-labelledby={headingId}
      className={`rounded-3xl border border-rule bg-card p-5 transition-opacity sm:p-8 ${stale ? "opacity-55" : "animate-rise"}`}
    >
      <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
        <div>
          <p className="flex items-center gap-2 text-xs font-semibold tracking-[0.18em] text-ink-faint uppercase">
            <StarMark className="size-3 text-gold" />
            Verdict · {describeFormat(evaluation.league_format)}
          </p>
          <h2
            id={headingId}
            className="mt-2 font-display text-4xl leading-tight font-semibold tracking-tight sm:text-5xl"
          >
            {HEADLINE[verdict]}
          </h2>
        </div>
        <p className="sm:text-right">
          <span
            className={`block font-display text-6xl leading-none font-semibold tracking-tight sm:text-7xl ${MARGIN_COLOUR[verdict]}`}
          >
            {formatPoints(margin)}
          </span>
          <span className="mt-2 block text-sm text-ink-muted">
            {verdict === "even" ? "value points apart" : "value points ahead"} ·{" "}
            {formatPercent(marginShare)} of the larger side
          </span>
        </p>
      </div>

      <BalanceBar
        a={evaluation.side_a.adjusted_total}
        b={evaluation.side_b.adjusted_total}
      />

      <Drivers drivers={evaluation.drivers} />

      <div className="mt-8 grid gap-8 md:grid-cols-2">
        <SideTable side="a" values={evaluation.side_a} />
        <SideTable side="b" values={evaluation.side_b} />
      </div>

      <p className="mt-8 border-t border-rule pt-4 text-xs leading-relaxed text-ink-muted">
        {METHOD_DESCRIPTION[evaluation.method]} Projections as of{" "}
        <time dateTime={evaluation.snapshot_date}>
          {formatSnapshotDate(evaluation.snapshot_date)}
        </time>
        .{" "}
        <Link
          href="/methodology"
          className="rounded-sm text-ink underline decoration-rule-strong underline-offset-2 hover:decoration-gold"
        >
          How the values work
        </Link>
      </p>
    </article>
  );
}

/**
 * Each side's share of the trade's adjusted value. The bar is decorative; the caption under
 * it carries the same numbers as text. The star marks 50%, where an even trade balances.
 */
function BalanceBar({ a, b }: { a: number; b: number }) {
  const total = a + b;
  // Values are never negative, so the only degenerate case is two worthless sides.
  const shareA = total > 0 ? a / total : 0.5;

  return (
    <figure className="mt-8">
      <div aria-hidden="true" className="relative">
        <div className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-well">
          <div
            className="bg-gold transition-[width] duration-500 ease-out"
            style={{ width: `${shareA * 100}%` }}
          />
          <div className="flex-1 bg-violet" />
        </div>
        <StarMark className="absolute top-1/2 left-1/2 size-5 -translate-x-1/2 -translate-y-1/2 text-ink" />
      </div>
      <figcaption className="mt-3 flex flex-wrap justify-between gap-x-6 gap-y-1 text-sm text-ink-muted">
        <span className="sr-only">
          Share of the trade&apos;s adjusted value:
        </span>
        <span>
          <span className="font-semibold text-ink">Team A</span>{" "}
          {formatPercent(shareA)} · {formatPoints(a)} points
        </span>
        <span>
          <span className="font-semibold text-ink">Team B</span>{" "}
          {formatPercent(1 - shareA)} · {formatPoints(b)} points
        </span>
      </figcaption>
    </figure>
  );
}

function Drivers({ drivers }: { drivers: Driver[] }) {
  const headingId = useId();
  if (drivers.length === 0) return null;

  return (
    <section aria-labelledby={headingId} className="mt-8">
      <h3
        id={headingId}
        className="text-xs font-semibold tracking-[0.18em] text-ink-faint uppercase"
      >
        Why
      </h3>
      <ul className="mt-3 space-y-3">
        {drivers.map((driver, index) => (
          <li
            // Drivers have no id; kind + side is unique within one verdict.
            key={`${driver.kind}-${driver.side ?? "none"}-${index}`}
            className="flex flex-col items-start gap-1.5 sm:flex-row sm:items-baseline sm:gap-3"
          >
            <DriverChip driver={driver} />
            <span className="text-sm text-ink-muted">{driver.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Value gaps (who comes out ahead) and depth discounts (an adjustment) look different. */
function DriverChip({ driver }: { driver: Driver }) {
  if (driver.kind === "value_gap") {
    return (
      <Chip tone="info">
        <svg viewBox="0 0 12 12" aria-hidden="true" className="size-3">
          <rect
            x="1.5"
            y="1.5"
            width="3.5"
            height="9"
            rx="1"
            fill="currentColor"
          />
          <rect
            x="7"
            y="5"
            width="3.5"
            height="5.5"
            rx="1"
            fill="currentColor"
          />
        </svg>
        Value gap {formatPoints(driver.amount)}
      </Chip>
    );
  }
  const team = driver.side !== null ? ` · ${TEAM_NAME[driver.side]}` : "";
  return (
    <Chip tone="neutral">
      <svg viewBox="0 0 12 12" aria-hidden="true" className="size-3">
        <path
          d="M2 3h8M2 6h5.5M2 9h3"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.5"
        />
      </svg>
      {`Depth discount${team} −${formatPoints(driver.amount)}`}
    </Chip>
  );
}

function SideTable({ side, values }: { side: TradeSide; values: SideValues }) {
  return (
    <table className="w-full text-sm">
      <caption className="mb-2 text-left font-display text-lg font-semibold">
        <span
          aria-hidden="true"
          className={`mr-2 inline-block size-2 rounded-full align-middle ${SIDE_DOT[side]}`}
        />
        {TEAM_NAME[side]} receives
      </caption>
      <thead>
        <tr className="border-b border-rule text-xs text-ink-faint">
          <th scope="col" className="py-2 text-left font-medium">
            Player
          </th>
          <th scope="col" className="py-2 pl-2 text-right font-medium">
            <span aria-hidden="true">Proj.</span>
            <span className="sr-only">Projected rest-of-season points</span>
          </th>
          <th scope="col" className="py-2 pl-2 text-right font-medium">
            Value
          </th>
          <th scope="col" className="py-2 pl-2 text-right font-medium">
            Rank
          </th>
        </tr>
      </thead>
      <tbody>
        {values.players.map((player) => (
          <tr key={player.player_id} className="border-b border-rule">
            <th scope="row" className="py-2.5 text-left font-normal">
              <span className="block font-medium text-ink">{player.name}</span>
              <span className="block text-xs text-ink-muted">
                {player.position} · {player.team ?? "FA"}
                {player.position_rank !== null
                  ? ` · ${player.position}${player.position_rank}`
                  : ""}
              </span>
            </th>
            <td className="py-2.5 pl-2 text-right text-ink-muted">
              {formatPoints(player.ros_points)}
            </td>
            <td className="py-2.5 pl-2 text-right font-semibold text-ink">
              {formatPoints(player.value)}
            </td>
            <td className="py-2.5 pl-2 text-right text-ink-muted">
              {player.overall_rank !== null ? (
                `#${player.overall_rank}`
              ) : (
                <>
                  <span aria-hidden="true">—</span>
                  <span className="sr-only">Unranked</span>
                </>
              )}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th
            scope="row"
            colSpan={2}
            className="pt-3 text-left font-normal text-ink-muted"
          >
            Raw total
          </th>
          <td className="pt-3 pl-2 text-right text-ink-muted">
            {formatPoints(values.raw_total)}
          </td>
          <td />
        </tr>
        <tr>
          <th scope="row" colSpan={2} className="pt-1 text-left font-semibold">
            Adjusted total
          </th>
          <td className="pt-1 pl-2 text-right font-semibold">
            {formatPoints(values.adjusted_total)}
          </td>
          <td />
        </tr>
      </tfoot>
    </table>
  );
}
