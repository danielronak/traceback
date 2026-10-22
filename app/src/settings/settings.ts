// Viewer preferences, kept in localStorage (a per-viewer convenience).

import { load, save } from "../storage";

export interface Settings {
  /** Show the fix straight away instead of hints first (D29): for teachers, or for review. */
  showFixes: boolean;
}

const DEFAULTS: Settings = { showFixes: false };

export function loadSettings(): Settings {
  return { ...DEFAULTS, ...(load<Partial<Settings>>("settings") ?? {}) };
}

export function saveSettings(settings: Settings): void {
  save("settings", settings);
}
