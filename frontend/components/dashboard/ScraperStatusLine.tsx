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
    const parts: string[] = [];
    if (status.lastDataDate) {
      const [y, m, d] = status.lastDataDate.split("-");
      parts.push(`Data updated ${m}/${d}/${y}`);
    }
    if (status.cookieAgeDays !== null) {
      parts.push(`Cookie age: ${status.cookieAgeDays}d`);
    }
    if (parts.length === 0) return null;
    const tone = status.isStale
      ? "text-amber-600 dark:text-amber-400"
      : "text-zinc-400 dark:text-zinc-500";
    return <p className={`text-xs ${tone}`}>{parts.join(". ")}.</p>;
  }

  // Desktop rendering: the richer "(current)" / "(N business days ago)" form.
  const pieces: string[] = [];
  if (status.lastDataDate) {
    const ageLabel =
      status.dataAgeBusinessDays === null
        ? ""
        : status.dataAgeBusinessDays === 0
          ? " (current)"
          : status.dataAgeBusinessDays === 1
            ? " (1 business day ago)"
            : ` (${status.dataAgeBusinessDays} business days ago)`;
    pieces.push(`Data last updated ${status.lastDataDate}${ageLabel}`);
  }
  if (status.cookieAgeDays !== null) {
    pieces.push(`cookie age: ${status.cookieAgeDays}d`);
  }
  if (pieces.length === 0) return null;

  const tone = status.isStale
    ? "text-amber-700 dark:text-amber-400"
    : "text-zinc-500 dark:text-zinc-400";

  return (
    <p className={`text-xs ${tone}`}>
      {pieces.join(" · ")}
      {status.isStale && " · cookie may need refresh in Railway"}
    </p>
  );
}
