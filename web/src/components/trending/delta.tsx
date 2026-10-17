import {
  formatSignedCount,
  formatSignedPoints,
} from "@/components/rankings/format";
import { Chip } from "@/components/ui/chip";

/**
 * A change shown three ways at once: arrow, sign, and colour. Colour alone would fail
 * colour-blind readers, so the arrow and the sign carry the meaning without it.
 */
export function Delta({
  change,
  unit,
}: {
  change: number;
  unit: "points" | "trades";
}) {
  const text =
    unit === "points" ? formatSignedPoints(change) : formatSignedCount(change);
  // Pick the direction from the number as displayed, so 0.04 can't show as "▲ 0.0".
  const shown =
    unit === "points" ? Math.round(change * 10) / 10 : Math.round(change);
  if (shown > 0) {
    return (
      <Chip tone="positive">
        <span aria-hidden="true">▲</span>
        {text}
      </Chip>
    );
  }
  if (shown < 0) {
    return (
      <Chip tone="negative">
        <span aria-hidden="true">▼</span>
        {text}
      </Chip>
    );
  }
  return <Chip>No change</Chip>;
}
