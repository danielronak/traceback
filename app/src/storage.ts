// Per-viewer conveniences (drafts, last mode) in localStorage. Storage can be
// missing or throw (private windows, blocked site data), and the app must work
// without it, so every access is guarded.

const PREFIX = "pymentor:";

export function load<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

export function save(key: string, value: unknown): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // Not saved; the app carries on.
  }
}
