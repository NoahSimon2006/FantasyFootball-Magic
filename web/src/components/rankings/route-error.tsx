"use client";

import { useEffect } from "react";

import { PageHeader } from "@/components/ui/page-header";

import { ACTION_CLASSES, StatePanel } from "./state-panel";

/**
 * The body of a route's error.tsx (shared with /trending). Expected failures, such as the
 * API being down, never get here: the data modules turn them into states. This is the
 * backstop for a bug while rendering, so it keeps the page's heading and offers a retry.
 */
export function RouteError({
  pageTitle,
  error,
  retry,
}: {
  pageTitle: string;
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <>
      <PageHeader title={pageTitle} />
      <StatePanel
        title="This page hit an unexpected error"
        action={
          <button type="button" className={ACTION_CLASSES} onClick={retry}>
            Try again
          </button>
        }
      >
        <p>
          Something broke while the page was being put together. Trying again
          fixes one-off problems; if it keeps happening, the server log has the
          details
          {error.digest ? ` (reference ${error.digest})` : ""}.
        </p>
      </StatePanel>
    </>
  );
}
