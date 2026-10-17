"use client";

import { RouteError } from "@/components/rankings/route-error";

export default function RankingsError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return <RouteError pageTitle="Player rankings" error={error} retry={retry} />;
}
