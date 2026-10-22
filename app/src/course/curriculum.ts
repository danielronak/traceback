// The curriculum files, bundled as text. The engine parses them (one parser, in
// Python), so the app never interprets TOML or lesson fences itself (D27).

const files = import.meta.glob(["../../../curriculum/course.toml", "../../../curriculum/*/*.{toml,md}"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

export const CURRICULUM_FILES: [string, string][] = Object.entries(files)
  .map(([path, text]): [string, string] => [path.slice(path.indexOf("curriculum/")), text])
  .sort(([a], [b]) => a.localeCompare(b));
