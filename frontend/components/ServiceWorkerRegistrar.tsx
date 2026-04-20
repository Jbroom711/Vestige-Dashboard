"use client";

import { useEffect } from "react";

/**
 * Registers /sw.js when the page first loads in a browser. Does nothing on
 * the server or in environments without service worker support.
 */
export default function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Registration failures are non-fatal — app still works without PWA.
    });
  }, []);
  return null;
}
