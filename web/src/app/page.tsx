import Link from "next/link";

import { StarMark } from "@/components/ui/star-mark";

// The verb says what you do on each page; it is the card's eyebrow, not decoration.
const FEATURES = [
  {
    href: "/calculator",
    action: "Evaluate",
    title: "Trade calculator",
    description:
      "Add what each team receives. Get a verdict, the margin in value points, and every reason behind it.",
  },
  {
    href: "/rankings",
    action: "Compare",
    title: "Rankings",
    description:
      "Every QB, RB, WR and TE ranked by value in your league's format, filterable by position.",
  },
  {
    href: "/trending",
    action: "Watch",
    title: "Trending",
    description:
      "The most-traded players, and whose value has risen or fallen since the last snapshot.",
  },
] as const;

export default function HomePage() {
  return (
    <>
      <section className="pt-14 pb-14 sm:pt-24 sm:pb-20">
        <p className="flex items-center gap-2 text-xs font-semibold tracking-[0.18em] text-gold-ink uppercase">
          <StarMark className="size-3.5 text-gold" />
          Redraft fantasy football
        </p>
        <h1 className="mt-5 max-w-4xl font-display text-5xl leading-[1.04] font-semibold tracking-tight text-balance sm:text-6xl lg:text-7xl">
          Who wins this trade, and by how much?
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-pretty text-ink-muted sm:text-xl">
          Fantasy Magic values every player for your league&apos;s format (team
          count, scoring and superflex), then weighs both sides of a trade and
          shows its working.
        </p>
        <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-4">
          <Link
            href="/calculator"
            className="inline-flex h-12 items-center rounded-full bg-gold px-6 font-semibold text-on-gold shadow-sm transition-[filter] hover:brightness-110"
          >
            Evaluate a trade
          </Link>
          <Link
            href="/rankings"
            className="rounded-sm font-medium text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-gold"
          >
            Browse the rankings
          </Link>
        </div>
      </section>

      <section aria-labelledby="features-title">
        <h2 id="features-title" className="sr-only">
          What you can do here
        </h2>
        <ul className="grid gap-4 md:grid-cols-3">
          {FEATURES.map(({ href, action, title, description }) => (
            // The whole card is clickable (the link's ::after covers it), but the link's
            // accessible name stays just the title. The card shows the link's focus ring.
            <li
              key={href}
              className="group relative flex flex-col rounded-2xl border border-rule bg-card p-6 transition-colors hover:border-gold has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-focus"
            >
              <p className="text-xs font-semibold tracking-[0.18em] text-ink-faint uppercase">
                {action}
              </p>
              <h3 className="mt-2 font-display text-2xl font-semibold">
                <Link
                  href={href}
                  className="outline-none after:absolute after:inset-0 after:rounded-2xl"
                >
                  {title}
                </Link>
              </h3>
              <p className="mt-3 flex-1 text-ink-muted">{description}</p>
              <span
                aria-hidden="true"
                className="mt-6 text-lg text-gold-ink transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
              >
                →
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-labelledby="how-title"
        className="mt-16 grid gap-10 rounded-3xl border border-rule bg-card p-6 sm:p-10 lg:grid-cols-[1fr_1.15fr]"
      >
        <div>
          <h2
            id="how-title"
            className="font-display text-3xl font-semibold tracking-tight"
          >
            How the values work{" "}
            <span className="font-normal text-ink-faint">(v0)</span>
          </h2>
          <p className="mt-4 text-ink-muted">
            A player&apos;s value is one number of fantasy points, worked out
            for your league&apos;s format:
          </p>
          <p className="mt-6 border-l-2 border-gold pl-4 font-display text-xl leading-snug sm:text-2xl">
            <i>value</i> = <i>projected rest-of-season points</i> −{" "}
            <i>replacement level</i>
          </p>
          <Link
            href="/methodology"
            className="mt-8 inline-block rounded-sm font-medium text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-gold"
          >
            Read the full methodology
          </Link>
        </div>
        <dl className="space-y-6">
          <div>
            <dt className="font-semibold">Replacement level</dt>
            <dd className="mt-1 text-ink-muted">
              What the best player left over at the same position would score
              once every team in your league has filled its starting lineup.
              More teams, PPR scoring or a superflex slot all move that line, so
              values change with your format.
            </dd>
          </div>
          <div>
            <dt className="font-semibold">Trades</dt>
            <dd className="mt-1 text-ink-muted">
              Each side&apos;s values are added up, with extra pieces
              discounted: two good players compete for the lineup spot one star
              fills. When the gap is small, the verdict is &ldquo;too close to
              call&rdquo; rather than a winner.
            </dd>
          </div>
          <div>
            <dt className="font-semibold">Coming next</dt>
            <dd className="mt-1 text-ink-muted">
              v0 uses projections only. Next, the model learns from real trades
              in public Sleeper leagues, so values also reflect what managers
              actually pay.
            </dd>
          </div>
        </dl>
      </section>
    </>
  );
}
