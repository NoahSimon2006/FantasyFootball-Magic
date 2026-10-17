import type { ReactNode } from "react";

/**
 * The top of a page: its one <h1>, an optional one-line description, and optional extra
 * content underneath (such as the league-format picker).
 */
export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="pt-10 pb-6 sm:pt-14 sm:pb-8">
      <h1 className="font-display text-4xl leading-tight font-semibold tracking-tight text-balance sm:text-5xl">
        {title}
      </h1>
      {description ? (
        <p className="mt-3 max-w-2xl text-lg text-ink-muted text-pretty">
          {description}
        </p>
      ) : null}
      {children ? <div className="mt-6">{children}</div> : null}
    </header>
  );
}
