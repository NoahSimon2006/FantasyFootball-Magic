"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/calculator", label: "Calculator" },
  { href: "/rankings", label: "Rankings" },
  { href: "/trending", label: "Trending" },
] as const;

/** True when `href` is the page being viewed, or a section that contains it. */
function isCurrent(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The main navigation, with the current page marked by `aria-current` (and a gold rule). */
export function SiteNav() {
  return <NavLinks pathname={usePathname()} />;
}

/**
 * The links themselves. `pathname: null` renders them with nothing marked current: the
 * fallback while the pathname is unknown (see SiteHeader).
 */
export function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Main" className="w-full md:w-auto">
      {/* Mobile: a full-width row of four equal tabs under the logo. md+: inline, right. */}
      <ul className="grid grid-cols-4 md:flex md:gap-1">
        {NAV_ITEMS.map(({ href, label }) => (
          <li key={href}>
            <Link
              href={href}
              aria-current={
                pathname !== null && isCurrent(pathname, href)
                  ? "page"
                  : undefined
              }
              className="relative flex h-11 items-center justify-center rounded-md px-2 text-sm font-medium text-ink-muted transition-colors hover:text-ink aria-[current=page]:text-ink aria-[current=page]:after:absolute aria-[current=page]:after:inset-x-2 aria-[current=page]:after:bottom-0 aria-[current=page]:after:h-0.5 aria-[current=page]:after:rounded-full aria-[current=page]:after:bg-gold md:h-16 md:px-3"
            >
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
