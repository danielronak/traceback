// The learner's progress, kept in IndexedDB on this device only (principle 3).
// Nothing here is ever sent anywhere; the learner can export feedback
// deliberately (see feedback.ts). If IndexedDB is unavailable (private
// windows, blocked storage), progress lives in memory for the session.

export interface Progress {
  lessons: Record<string, { readAt: number }>;
  exercises: Record<string, { attempts: number; passedAt: number | null }>;
  /** How often each rule card has come up. `sincePractice` resets after a quiz. */
  mistakes: Record<string, { count: number; sincePractice: number; lastSeen: number }>;
}

export const EMPTY: Progress = { lessons: {}, exercises: {}, mistakes: {} };

const DB = "pymentor";
const STORE = "kv";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/** A tiny key-value store over IndexedDB that falls back to memory. */
export class KeyValueStore {
  private db: Promise<IDBDatabase | null>;
  private memory = new Map<string, unknown>();

  constructor() {
    this.db = (typeof indexedDB === "undefined" ? Promise.reject() : open()).catch(() => null);
  }

  async get<T>(key: string): Promise<T | undefined> {
    const db = await this.db;
    if (!db) return this.memory.get(key) as T | undefined;
    return new Promise((resolve) => {
      const request = db.transaction(STORE).objectStore(STORE).get(key);
      request.onsuccess = () => resolve(request.result as T | undefined);
      request.onerror = () => resolve(this.memory.get(key) as T | undefined);
    });
  }

  async set(key: string, value: unknown): Promise<void> {
    this.memory.set(key, value);
    const db = await this.db;
    if (!db) return;
    await new Promise<void>((resolve) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).put(value, key);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => resolve(); // kept in memory; the app carries on
    });
  }
}

export const PRACTICE_AFTER = 3; // repetition becomes practice after this many

export function practiceDue(progress: Progress, cardId: string): boolean {
  return (progress.mistakes[cardId]?.sincePractice ?? 0) >= PRACTICE_AFTER;
}

// --- pure updates, so they're easy to test ---------------------------------------

export function lessonRead(progress: Progress, id: string, now = Date.now()): Progress {
  if (progress.lessons[id]) return progress;
  return { ...progress, lessons: { ...progress.lessons, [id]: { readAt: now } } };
}

export function exerciseAttempted(progress: Progress, id: string, passed: boolean, now = Date.now()): Progress {
  const before = progress.exercises[id] ?? { attempts: 0, passedAt: null };
  const after = { attempts: before.attempts + 1, passedAt: before.passedAt ?? (passed ? now : null) };
  return { ...progress, exercises: { ...progress.exercises, [id]: after } };
}

export function mistakesSeen(progress: Progress, cardIds: string[], now = Date.now()): Progress {
  if (cardIds.length === 0) return progress;
  const mistakes = { ...progress.mistakes };
  for (const id of cardIds) {
    const before = mistakes[id] ?? { count: 0, sincePractice: 0, lastSeen: 0 };
    mistakes[id] = { count: before.count + 1, sincePractice: before.sincePractice + 1, lastSeen: now };
  }
  return { ...progress, mistakes };
}

export function practised(progress: Progress, cardId: string): Progress {
  const before = progress.mistakes[cardId];
  if (!before) return progress;
  return { ...progress, mistakes: { ...progress.mistakes, [cardId]: { ...before, sincePractice: 0 } } };
}

/**
 * Which mistakes are new in this report, compared with the last one for the
 * same piece of code. A mistake that stays on screen while the learner types
 * around it is one mistake, not one per keystroke.
 */
export function newMistakes(previous: Set<string>, current: { card: string; key: string }[]): string[] {
  return current.filter((m) => !previous.has(m.key)).map((m) => m.card);
}
