import { Chip } from "@/components/ui/chip";

/** What "value" means, in plain English, plus an honest note on what v0 leaves out. */
export function ValueExplainer() {
  return (
    <section
      aria-labelledby="value-explainer-title"
      className="border-t border-rule pt-8"
    >
      <h2
        id="value-explainer-title"
        className="font-display text-2xl font-semibold text-ink"
      >
        What “value” means
      </h2>
      <div className="mt-4 grid max-w-4xl gap-x-10 gap-y-4 text-pretty text-ink-muted md:grid-cols-2">
        <p>
          Value is how many more fantasy points a player is projected to score
          over the rest of the season than a replacement: the best player at his
          position who wouldn’t start for any team in your league, roughly
          what’s left on waivers. A value of 0 means waiver-level.
        </p>
        <p>
          Your format changes the answer. More teams start more players, so the
          leftovers get worse and every starter’s edge grows. PPR adds points
          for catches. Superflex lets each team start a second quarterback,
          which drains the QB pool and lifts every starting QB.
        </p>
      </div>
      <p className="mt-6 flex max-w-4xl flex-wrap items-baseline gap-x-2 gap-y-1 text-sm text-ink-muted">
        <Chip tone="info">v0: projections only</Chip>
        <span>
          These values come from Sleeper’s projections alone. Evidence from real
          trades in public Sleeper leagues is coming next and will be blended
          in.
        </span>
      </p>
    </section>
  );
}
