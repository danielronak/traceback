// Mapping engine positions (1-based lines, 0-based columns) to editor offsets.

import type { Diagnostic } from "../engine/types";

export interface DocLike {
  lines: number;
  line(n: number): { from: number; to: number; text: string };
}

const clamp = (n: number, low: number, high: number) => Math.min(Math.max(n, low), high);

/** The range to underline for a diagnostic. Never empty unless the line is. */
export function diagnosticRange(doc: DocLike, d: Diagnostic): { from: number; to: number } {
  const line = doc.line(clamp(d.line, 1, doc.lines));
  let from = line.from + clamp(d.col, 0, line.text.length);
  let to: number;
  if (d.end_line != null && d.end_col != null) {
    const end = doc.line(clamp(d.end_line, 1, doc.lines));
    to = end.from + clamp(d.end_col, 0, end.text.length);
  } else {
    // No end position: underline the word Python pointed at.
    const word = /^\w+/.exec(line.text.slice(from - line.from));
    to = Math.min(from + (word ? word[0].length : 1), line.to);
  }
  // A one-character range on a comment's `#` (Python's "expected ':'" before a
  // comment) means the same as pointing just past the code.
  const atComment = to - from === 1 && line.text[from - line.from] === "#";
  if (to <= from || atComment) {
    // Python points just past the code for things like "expected ':'"; underline
    // the last character before that point instead (skipping spaces).
    let at = from - line.from;
    while (at > 0 && line.text[at - 1] === " ") at -= 1;
    if (at > 0) {
      from = line.from + at - 1;
      to = from + 1;
    } else {
      to = Math.min(from + 1, line.to);
    }
  }
  return { from, to };
}

/** A stable key for a finding, used to remember a card's hint-ladder state. */
export function findingKey(d: Diagnostic): string {
  return `${d.severity}:${d.code}:${d.line}:${d.message}`;
}
