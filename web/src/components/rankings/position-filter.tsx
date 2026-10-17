import Link from "next/link";

import { hrefWith, type SearchParams } from "./href";
import {
  CONTROL_LABEL_CLASSES,
  PILL_CLASSES,
  PILL_CURRENT_CLASSES,
  PILL_IDLE_CLASSES,
} from "./styles";
import { POSITIONS, type Position } from "./types";

const OPTIONS: readonly { label: string; position: Position | undefined }[] = [
  { label: "All", position: undefined },
  ...POSITIONS.map((position) => ({ label: position, position })),
];

/**
 * All / QB / RB / WR / TE as links, so each filtered view has its own URL. A link keeps the
 * league format and any other params, and drops `offset`: page 3 of everyone is not page 3
 * of the quarterbacks.
 */
export function PositionFilter({
  search,
  current,
}: {
  search: SearchParams;
  current: Position | undefined;
}) {
  return (
    <nav aria-labelledby="position-filter-label">
      <p id="position-filter-label" className={CONTROL_LABEL_CLASSES}>
        Position
      </p>
      <ul className="flex flex-wrap gap-2">
        {OPTIONS.map(({ label, position }) => {
          const isCurrent = position === current;
          return (
            <li key={label}>
              <Link
                href={hrefWith("/rankings", search, {
                  position: position ?? null,
                  offset: null,
                })}
                aria-current={isCurrent ? "true" : undefined}
                className={`${PILL_CLASSES} ${isCurrent ? PILL_CURRENT_CLASSES : PILL_IDLE_CLASSES}`}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
