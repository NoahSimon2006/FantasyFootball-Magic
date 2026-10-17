// Class lists shared by the /rankings and /trending tables and filter links, so both pages
// read as one product. All colours are theme tokens from globals.css.

/** The scrollable frame around a data table; it scrolls sideways only if text is zoomed. */
export const TABLE_FRAME_CLASSES =
  "overflow-x-auto rounded-2xl border border-rule bg-card";
export const TABLE_HEAD_CLASSES =
  "px-2 py-3 text-xs font-semibold tracking-wide text-ink-muted uppercase sm:px-4";
export const TABLE_CELL_CLASSES = "px-2 py-3 align-middle sm:px-4";

/** A filter option drawn as a pill: idle ones are outlined, the current one is filled. */
export const PILL_CLASSES =
  "inline-flex h-9 min-w-12 items-center justify-center rounded-full border px-3.5 text-sm font-semibold";
export const PILL_IDLE_CLASSES =
  "border-rule-strong bg-card text-ink hover:bg-well";
export const PILL_CURRENT_CLASSES = "border-gold bg-gold text-on-gold";

/** The small uppercase label above a control group, matching the format picker's labels. */
export const CONTROL_LABEL_CLASSES =
  "mb-1 text-xs font-semibold tracking-wide text-ink-muted uppercase";
