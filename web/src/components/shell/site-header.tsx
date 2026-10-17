import Link from "next/link";
import { Suspense } from "react";

import { StarMark } from "@/components/ui/star-mark";

import { NavLinks, SiteNav } from "./site-nav";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between px-4 sm:px-6 md:flex-nowrap lg:px-8">
        <Link
          href="/"
          className="flex h-14 items-center gap-2 rounded-md font-display text-lg font-semibold tracking-tight md:h-16"
        >
          <StarMark className="size-5 text-gold" />
          Fantasy Magic
        </Link>
        {/* usePathname() can suspend under any future route with unknown dynamic params
            (cacheComponents). The boundary keeps the rest of the header prerendered. */}
        <Suspense fallback={<NavLinks pathname={null} />}>
          <SiteNav />
        </Suspense>
      </div>
    </header>
  );
}
