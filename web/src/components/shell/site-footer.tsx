import Link from "next/link";

import { StarMark } from "@/components/ui/star-mark";

const FOOTER_LINKS = [
  { href: "/calculator", label: "Calculator" },
  { href: "/rankings", label: "Rankings" },
  { href: "/trending", label: "Trending" },
  { href: "/methodology", label: "Methodology" },
] as const;

const LINK_CLASSES =
  "rounded-sm text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-gold";

export function SiteFooter() {
  return (
    <footer className="border-t border-rule">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-ink-muted sm:px-6 md:flex-row md:justify-between lg:px-8">
        <div className="max-w-xl space-y-2">
          <p className="flex items-center gap-2 font-display text-base font-semibold text-ink">
            <StarMark className="size-4 text-gold" />
            Fantasy Magic
          </p>
          <p>
            Values are experimental: model v0 uses projections only, not yet
            real trades. See the{" "}
            <Link href="/methodology" className={LINK_CLASSES}>
              methodology
            </Link>{" "}
            for what that means.
          </p>
          {/* Sleeper's terms ask for this credit wherever its data is shown. */}
          <p>
            Player and league data from{" "}
            <a href="https://sleeper.com" className={LINK_CLASSES}>
              Sleeper
            </a>
            . Not affiliated with Sleeper.
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-x-5 gap-y-2 md:flex-col md:items-end">
            {FOOTER_LINKS.map(({ href, label }) => (
              <li key={href}>
                <Link
                  href={href}
                  className="rounded-sm hover:text-ink hover:underline hover:underline-offset-4"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
