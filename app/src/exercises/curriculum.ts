// The exercise files, bundled as text. The engine parses them (one parser, in
// Python), so the app never interprets TOML itself.

const files = import.meta.glob("../../../curriculum/exercises/*.toml", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

export const EXERCISE_FILES: [string, string][] = Object.entries(files)
  .map(([path, text]): [string, string] => [path.slice(path.indexOf("curriculum/")), text])
  .sort(([a], [b]) => a.localeCompare(b));
