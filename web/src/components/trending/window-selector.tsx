import Link from "next/link";

import { hrefWith, type SearchParams } from "@/components/rankings/href";
import {
  CONTROL_LABEL_CLASSES,
  PILL_CLASSES,
  PILL_CURRENT_CLASSES,
  PILL_IDLE_CLASSES,
} from "@/components/rankings/styles";

import { DEFAULT_WINDOW, TRENDING_WINDOWS, type TrendingWindow } from "./types";

/** "7 days / 14 days" as links that keep the league format and any other params. */
export function WindowSelector({
  search,
  current,
}: {
  search: SearchParams;
  current: TrendingWindow;
}) {
  return (
    <nav aria-labelledby="window-selector-label">
      <p id="window-selector-label" className={CONTROL_LABEL_CLASSES}>
        Window
      </p>
      <ul className="flex flex-wrap gap-2">
        {TRENDING_WINDOWS.map((days) => {
          const isCurrent = days === current;
          return (
            <li key={days}>
              <Link
                href={hrefWith("/trending", search, {
                  days: days === DEFAULT_WINDOW ? null : String(days),
                })}
                aria-current={isCurrent ? "true" : undefined}
                className={`${PILL_CLASSES} ${isCurrent ? PILL_CURRENT_CLASSES : PILL_IDLE_CLASSES}`}
              >
                {days} days
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
