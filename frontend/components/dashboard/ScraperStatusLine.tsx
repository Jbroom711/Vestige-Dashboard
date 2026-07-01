"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useIsMobile } from "@/lib/useIsMobile";

interface ScraperStatus {
  lastDataDate: string | null;
  dataAgeBusinessDays: number | null;
  cookieSetAt: string | null;
  cookieAgeDays: number | null;
  isStale: boolean;
}

/**
 * Small subtitle line under the dashboard header that surfaces the nightly
 * vhg.app scrape's freshness, plus the age of the stored cookie. Renders
 * yellow/red when stale so the user notices without having to read Railway
 * logs.
 */
export default function ScraperStatusLine() {
  const [status, setStatus] = useState<ScraperStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isMobile = useIsMobile();

  useEffect(() => {
    let mounted = true;
    api
      .get<ScraperStatus>("/scraper/status")
      .then((s) => {
        if (mounted) setStatus(s);
      })
      .catch((e: unknown) => {
        if (mounted) setError(e instanceof Error ? e.message : "status fetch failed");
      });
    return () => {
      mounted = false;
    };
  }, []);

  if (error || !status) return null;

  // Mobile rendering: terser format, lighter grey than the top-row labels.
  if (isMobile) {
    if (!status.lastDataDate) return null;
    const [y, m, d] = status.lastDataDate.split("-");
    const tone = status.isStale
      ? "text-amber-600 dark:text-amber-400"
      : "text-zinc-300 dark:text-zinc-600";
    return <p className={`text-xs ${tone}`}>Data updated {m}/{d}/{y}.</p>;
  }

  // Desktop rendering: the richer "(current)" / "(N business days ago)" form.
  if (!status.lastDataDate) return null;
  const ageLabel =
    status.dataAgeBusinessDays === null
      ? ""
      : status.dataAgeBusinessDays === 0
        ? " (current)"
        : status.dataAgeBusinessDays === 1
          ? " (1 business day ago)"
          : ` (${status.dataAgeBusinessDays} business days ago)`;

  const tone = status.isStale
    ? "text-amber-700 dark:text-amber-400"
    : "text-zinc-500 dark:text-zinc-400";

  return (
    <p className={`text-xs ${tone}`}>
      Data last updated {status.lastDataDate}{ageLabel}
    </p>
  );
}
