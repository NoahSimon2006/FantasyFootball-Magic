import type { MethodologyResult } from "./data";

/** Display order for Sleeper's starting-slot codes; unknown codes go last, alphabetically. */
const SLOT_ORDER = [
  "QB",
  "RB",
  "WR",
  "TE",
  "WRRB_FLEX",
  "REC_FLEX",
  "FLEX",
  "SUPER_FLEX",
];

const SLOT_LABELS: Record<string, string> = {
  WRRB_FLEX: "RB/WR flex",
  REC_FLEX: "WR/TE flex",
  FLEX: "FLEX",
  SUPER_FLEX: "Superflex",
};

function slotRank(slot: string): number {
  const index = SLOT_ORDER.indexOf(slot);
  return index === -1 ? SLOT_ORDER.length : index;
}

export function describeLineup(slots: Record<string, number>): string {
  return Object.entries(slots)
    .filter(([, count]) => count > 0)
    .sort(([a], [b]) => slotRank(a) - slotRank(b) || a.localeCompare(b))
    .map(([slot, count]) => `${SLOT_LABELS[slot] ?? slot} ${count}`)
    .join(" · ");
}

function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

function count(value: number): string {
  return value.toLocaleString("en-US");
}

/** The model's live parameters and data counts, or an honest note when they can't load. */
export function LiveNumbers({ result }: { result: MethodologyResult }) {
  if (result.kind === "error") {
    return (
      <div
        role="status"
        className="rounded-2xl border border-rule bg-well p-6 text-ink-muted"
      >
        <p className="font-semibold text-ink">Live numbers unavailable</p>
        <p className="mt-1">
          The API couldn&apos;t be reached, so the exact settings and data
          counts can&apos;t be shown right now. The method described on this
          page doesn&apos;t change; the numbers will appear here once the API is
          back.
        </p>
      </div>
    );
  }

  const { parameters, data } = result.data;
  const settings: Array<[string, string]> = [
    [
      "Depth discount",
      `each extra player on a side counts ${percent(parameters.depth_decay)} of the one before`,
    ],
    [
      "Too close to call",
      `gaps under ${percent(parameters.even_threshold)} of the larger side`,
    ],
    [
      "Projections counted",
      `from this week through week ${parameters.last_fantasy_week}`,
    ],
    ["Positions valued", parameters.valued_positions.join(", ")],
    [
      "Default league",
      `${parameters.default_teams} teams, ${parameters.default_ppr} point per reception`,
    ],
    ["Lineup (1QB)", describeLineup(parameters.lineup_1qb.slots)],
    ["Lineup (superflex)", describeLineup(parameters.lineup_superflex.slots)],
  ];
  const freshness: Array<[string, string]> = [
    [
      "Latest projections",
      data.latest_projection_snapshot ?? "none loaded yet",
    ],
    ["Days of projection history", count(data.projection_snapshots)],
    ["Players", count(data.players)],
    ["Leagues sampled", count(data.leagues)],
    ["Trades collected", count(data.trades)],
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <NumberCard title="Settings in use" rows={settings} />
      <NumberCard title="Data behind them" rows={freshness} />
    </div>
  );
}

function NumberCard({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, string]>;
}) {
  return (
    <section
      aria-label={title}
      className="rounded-2xl border border-rule bg-card p-6"
    >
      <h3 className="text-sm font-semibold tracking-wide text-gold-ink uppercase">
        {title}
      </h3>
      <dl className="mt-4 space-y-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-sm text-ink-muted">{label}</dt>
            <dd className="font-medium text-ink tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
