"use client";

import { useEffect, useState } from "react";

/**
 * SSR-safe matchMedia hook. Returns false on first render (the desktop default)
 * then reflects the real viewport on the client. Used to gate mobile-only
 * Recharts prop values that can't be expressed in Tailwind responsive classes.
 */
export function useIsMobile(breakpoint = 640): boolean {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const handler = () => setIsMobile(mq.matches);
    handler();
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [breakpoint]);
  return isMobile;
}
