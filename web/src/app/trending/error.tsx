"use client";

import { RouteError } from "@/components/rankings/route-error";

export default function TrendingError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <RouteError pageTitle="Trending players" error={error} retry={retry} />
  );
}
