// Number and date formatting shared by /rankings and /trending (see href.ts for why it
// lives in this folder). Fixed to en-US so server output never varies by machine locale.

const POINTS = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const SIGNED_POINTS = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

const SIGNED_COUNT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
  signDisplay: "exceptZero",
});

const COUNT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

// The API sends calendar dates ("2026-10-14"). Formatting them in UTC keeps the day the API
// meant; a local time zone west of UTC would show the day before.
const CALENDAR_DATE = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeZone: "UTC",
});

/** A typographic minus lines up with "+" and is read as "minus" by screen readers. */
function withMinusSign(text: string): string {
  return text.replace("-", "−");
}

/** Fantasy points with one decimal: "182.4", "1,204.0". */
export function formatPoints(points: number): string {
  return withMinusSign(POINTS.format(points));
}

/** A change in points with its sign spelled out: "+6.2", "−3.0", "0.0". */
export function formatSignedPoints(change: number): string {
  return withMinusSign(SIGNED_POINTS.format(change));
}

/** A whole count: "1,024". */
export function formatCount(count: number): string {
  return COUNT.format(count);
}

/** A change in a count with its sign spelled out: "+4", "−2", "0". */
export function formatSignedCount(change: number): string {
  return withMinusSign(SIGNED_COUNT.format(change));
}

/** "2026-10-14" becomes "Oct 14, 2026"; anything unparseable is shown as given. */
export function formatDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? isoDate : CALENDAR_DATE.format(date);
}
