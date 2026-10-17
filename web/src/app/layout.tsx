import type { Metadata, Viewport } from "next";

import { SiteFooter } from "@/components/shell/site-footer";
import { SiteHeader } from "@/components/shell/site-header";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Fantasy Magic",
    template: "%s · Fantasy Magic",
  },
  description:
    "Redraft fantasy football trade values for your league's format: a trade calculator, rankings, and trending players.",
};

// Browser chrome (mobile address bar) matches the page background in either theme.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f2e9" },
    { media: "(prefers-color-scheme: dark)", color: "#0e0c24" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="flex flex-col">
        <a
          href="#main"
          className="sr-only rounded-md bg-card px-4 py-2 font-medium text-ink shadow-lg focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50"
        >
          Skip to content
        </a>
        <SiteHeader />
        {/* tabIndex -1 lets the skip link move focus here; pages render inside, no <main> of their own. */}
        <main
          id="main"
          tabIndex={-1}
          className="mx-auto w-full max-w-6xl flex-1 px-4 pb-20 outline-none sm:px-6 lg:px-8"
        >
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
