"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, useOptimistic, useTransition } from "react";

import {
  formatToQuery,
  PPR_OPTIONS,
  TEAM_OPTIONS,
  type LeagueFormatParams,
  type PprValue,
} from "@/lib/league-format";

/**
 * League-format controls (team count, scoring, superflex) that live in the URL: changing one
 * rewrites `teams`, `ppr` and `superflex` in the query string and keeps every other param, so
 * the page re-renders for the new format and the link stays shareable.
 *
 * `format` is the format the page parsed from its own `searchParams` (see parseFormatParams).
 */
export function FormatPicker({ format }: { format: LeagueFormatParams }) {
  // With cacheComponents, useSearchParams() suspends while a route is prerendered. The
  // boundary lives here so callers can place <FormatPicker> anywhere without one. The
  // fallback is the same controls, disabled, so the prerendered layout doesn't shift.
  return (
    <Suspense fallback={<FormatControls format={format} disabled />}>
      <UrlFormatPicker format={format} />
    </Suspense>
  );
}

function UrlFormatPicker({ format }: { format: LeagueFormatParams }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  // The new format only reaches `format` once the navigation finishes (the server re-reads
  // the URL). Showing it optimistically keeps a just-changed control from snapping back.
  const [shownFormat, setShownFormat] = useOptimistic(format);

  function update(change: Partial<LeagueFormatParams>) {
    const next = { ...shownFormat, ...change };
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(formatToQuery(next))) {
      params.set(key, String(value));
    }
    startTransition(() => {
      setShownFormat(next);
      // replace, not push: flipping a setting shouldn't add a Back-button step per click.
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    });
  }

  return (
    <FormatControls
      format={shownFormat}
      onChange={update}
      pending={isPending}
    />
  );
}

const SELECT_CLASSES =
  "h-10 w-full rounded-lg border border-rule-strong bg-card px-3 text-sm text-ink disabled:opacity-60";

function FormatControls({
  format,
  onChange,
  disabled = false,
  pending = false,
}: {
  format: LeagueFormatParams;
  onChange?: (change: Partial<LeagueFormatParams>) => void;
  disabled?: boolean;
  pending?: boolean;
}) {
  const id = useId();

  return (
    <fieldset
      className="flex flex-wrap items-end gap-x-4 gap-y-3"
      disabled={disabled}
      aria-busy={pending}
    >
      <legend className="sr-only">League format</legend>

      <div className="w-36">
        <label
          htmlFor={`${id}-teams`}
          className="mb-1 block text-xs font-semibold tracking-wide text-ink-muted uppercase"
        >
          League size
        </label>
        <select
          id={`${id}-teams`}
          className={SELECT_CLASSES}
          value={format.teams}
          onChange={(event) =>
            onChange?.({ teams: Number(event.target.value) })
          }
        >
          {TEAM_OPTIONS.map((teams) => (
            <option key={teams} value={teams}>
              {teams} teams
            </option>
          ))}
        </select>
      </div>

      <div className="w-36">
        <label
          htmlFor={`${id}-ppr`}
          className="mb-1 block text-xs font-semibold tracking-wide text-ink-muted uppercase"
        >
          Scoring
        </label>
        <select
          id={`${id}-ppr`}
          className={SELECT_CLASSES}
          value={format.ppr}
          onChange={(event) =>
            onChange?.({ ppr: Number(event.target.value) as PprValue })
          }
        >
          {PPR_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* A real checkbox (a checkbox to assistive tech, Space toggles it) drawn as a switch.
          Track and knob are both siblings of the input so plain `peer-*` variants reach them. */}
      <label className="flex h-10 cursor-pointer items-center gap-2.5 text-sm font-medium text-ink has-disabled:cursor-default">
        <span className="relative inline-flex h-6 w-10 shrink-0">
          <input
            type="checkbox"
            className="peer sr-only"
            checked={format.superflex}
            onChange={(event) =>
              onChange?.({ superflex: event.target.checked })
            }
          />
          <span
            aria-hidden="true"
            className="absolute inset-0 rounded-full border border-rule-strong bg-well transition-colors peer-checked:border-gold peer-checked:bg-gold peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus peer-disabled:opacity-60 motion-reduce:transition-none"
          />
          <span
            aria-hidden="true"
            className="absolute top-1 left-1 size-4 rounded-full bg-ink-muted transition-transform peer-checked:translate-x-4 peer-checked:bg-on-gold motion-reduce:transition-none"
          />
        </span>
        Superflex
      </label>

      <p
        className="h-10 content-center text-xs text-ink-muted"
        aria-live="polite"
      >
        {pending ? "Updating…" : ""}
      </p>
    </fieldset>
  );
}
