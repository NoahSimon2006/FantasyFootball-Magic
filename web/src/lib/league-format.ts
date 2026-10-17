// League format = the three settings that change what a player is worth in a trade: how many
// teams share the player pool, how receptions are scored, and whether a second QB slot exists.
// Pages keep it in the URL (?teams=10&ppr=0.5&superflex=true) so a link reproduces a view.
// Everything here is pure: no React, no Next.js, no I/O.

/** Points per reception. The API accepts exactly these three. */
export type PprValue = 0 | 0.5 | 1;

export interface LeagueFormatParams {
  teams: number;
  ppr: PprValue;
  superflex: boolean;
}

/** Twelve-team, full PPR, one QB: the most common redraft setup. */
export const DEFAULT_FORMAT: Readonly<LeagueFormatParams> = {
  teams: 12,
  ppr: 1,
  superflex: false,
};

/**
 * The team counts the UI offers. The API accepts 2 to 32; the picker (and so the parser) sticks
 * to common sizes so a control always shows the format that is actually being used.
 */
export const TEAM_OPTIONS = [8, 10, 12, 14, 16] as const;

export const PPR_OPTIONS: readonly { value: PprValue; label: string }[] = [
  { value: 1, label: "Full PPR" },
  { value: 0.5, label: "Half PPR" },
  { value: 0, label: "Standard" },
];

type SearchParamsRecord = Record<string, string | string[] | undefined>;

/** `?x=1&x=2` arrives as an array; the first value wins, like most servers. */
function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parseTeams(raw: string | undefined): number | undefined {
  // Strict digits only: Number("") is 0 and Number("0x10") is 16, neither is a team count.
  if (raw === undefined || !/^\d+$/.test(raw.trim())) return undefined;
  const teams = Number(raw);
  return TEAM_OPTIONS.find((option) => option === teams);
}

function parsePpr(raw: string | undefined): PprValue | undefined {
  // Decimal literals only ("1", "0.5", ".5"). Number("") is 0 and would read as Standard.
  if (raw === undefined || !/^(\d+\.?\d*|\.\d+)$/.test(raw.trim()))
    return undefined;
  const ppr = Number(raw);
  return PPR_OPTIONS.find((option) => option.value === ppr)?.value;
}

function parseSuperflex(raw: string | undefined): boolean | undefined {
  // "on" is what a plain HTML checkbox submits, so a no-JavaScript <form> would still work.
  switch (raw?.trim().toLowerCase()) {
    case "true":
    case "1":
    case "on":
    case "yes":
      return true;
    case "false":
    case "0":
    case "off":
    case "no":
      return false;
    default:
      return undefined;
  }
}

/**
 * Reads a format from URL query params. Tolerant by design: URLs are user input, so each
 * field that is missing or invalid falls back to its own default and never throws or rejects
 * the whole format.
 */
export function parseFormatParams(
  search: SearchParamsRecord,
): LeagueFormatParams {
  return {
    teams: parseTeams(firstValue(search.teams)) ?? DEFAULT_FORMAT.teams,
    ppr: parsePpr(firstValue(search.ppr)) ?? DEFAULT_FORMAT.ppr,
    superflex:
      parseSuperflex(firstValue(search.superflex)) ?? DEFAULT_FORMAT.superflex,
  };
}

/** The format as the API's query/body fields (`teams`, `ppr`, `superflex`). */
export function formatToQuery(format: LeagueFormatParams): {
  teams: number;
  ppr: number;
  superflex: boolean;
} {
  return { teams: format.teams, ppr: format.ppr, superflex: format.superflex };
}

/**
 * A short human label, e.g. "12-team · Full PPR · 1QB". Takes `ppr: number` (not PprValue)
 * so it also describes the `league_format` an API response echoes back.
 */
export function describeFormat(format: {
  teams: number;
  ppr: number;
  superflex: boolean;
}): string {
  const scoring =
    PPR_OPTIONS.find((option) => option.value === format.ppr)?.label ??
    `${format.ppr} PPR`;
  return [
    `${format.teams}-team`,
    scoring,
    format.superflex ? "Superflex" : "1QB",
  ].join(" · ");
}
