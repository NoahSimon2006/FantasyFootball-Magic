import type { ReactNode } from "react";

export type ChipTone = "neutral" | "positive" | "negative" | "info";

// Each tone is a tinted fill + matching text + a faint border, all from the tokens in
// globals.css, so every chip follows the light/dark theme on its own.
const TONE_CLASSES: Record<ChipTone, string> = {
  neutral: "bg-well text-ink-muted border-rule",
  positive: "bg-positive-soft text-positive border-positive/30",
  negative: "bg-negative-soft text-negative border-negative/30",
  info: "bg-violet-soft text-violet border-violet/30",
};

/**
 * A small pill label. Colour is only a reinforcement: put the meaning in the text
 * (for example "+3.2" or "Rising"), never in the tone alone.
 */
export function Chip({
  tone = "neutral",
  children,
}: {
  tone?: ChipTone;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}
