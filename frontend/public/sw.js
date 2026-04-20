// Minimal service worker — installs immediately, takes control on activate,
// no runtime caching yet. Enough to satisfy the PWA installability check
// (browsers want a SW at the scope root). Expand with caching strategies
// once the data layer is wired up.

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
  // No-op: default network behavior.
});
