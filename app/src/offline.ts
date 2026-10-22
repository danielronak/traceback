// Registers the service worker (production builds only; in development it
// would serve stale files).

const RELOADED = "pymentor:isolation-reload";

export function registerServiceWorker() {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  const sw = navigator.serviceWorker;
  // On a host that can't send the isolation headers, the first visit isn't
  // isolated. Once our worker controls the page it adds them, so reload once.
  const reloadIfNeeded = () => {
    if (self.crossOriginIsolated || !sw.controller) return;
    try {
      if (sessionStorage.getItem(RELOADED)) return;
      sessionStorage.setItem(RELOADED, "1");
    } catch {
      return; // without sessionStorage we can't guard against a reload loop
    }
    location.reload();
  };
  if (sw.controller) reloadIfNeeded();
  else sw.addEventListener("controllerchange", reloadIfNeeded, { once: true });
  sw.register(`${import.meta.env.BASE_URL}sw.js`);
}
