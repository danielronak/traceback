// PyMentor's service worker. Generated at build time from this template by
// vite.config.ts, which fills in the version and the list of files to cache.

const VERSION = __VERSION__;
const PRECACHE = __PRECACHE__;
const CACHE = `pymentor-${VERSION}`;

// input() needs cross-origin isolation (SharedArrayBuffer). Adding the headers
// here means it also works on hosts that can't set them.
const ISOLATION = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
  "Cross-Origin-Resource-Policy": "same-origin",
};

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
  // No skipWaiting(): a new version takes over on the next visit, so a page
  // that's already open never loses files it still needs.
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("pymentor-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isolated(response) {
  if (!response || response.type === "opaque" || response.status === 0) return response;
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(ISOLATION)) headers.set(name, value);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE);
      // Pages: the cached app shell, so the app opens offline.
      const key = request.mode === "navigate" ? "./" : request;
      // ignoreVary: module scripts carry an Origin header the precache requests
      // didn't, and servers often send "Vary: Origin". These are all our own
      // static files, so the variation never matters.
      const cached = await cache.match(key, { ignoreSearch: true, ignoreVary: true });
      if (cached) return isolated(cached);
      try {
        return isolated(await fetch(request));
      } catch (error) {
        const shell = request.mode === "navigate" ? await cache.match("./", { ignoreVary: true }) : undefined;
        if (shell) return isolated(shell);
        throw error;
      }
    })(),
  );
});
