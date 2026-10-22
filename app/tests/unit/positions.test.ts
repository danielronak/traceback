import { describe, expect, it } from "vitest";
import { diagnosticRange, type DocLike } from "../../src/editor/positions";
import type { Diagnostic } from "../../src/engine/types";

function doc(text: string): DocLike {
  const lines = text.split("\n");
  const starts: number[] = [];
  let offset = 0;
  for (const line of lines) {
    starts.push(offset);
    offset += line.length + 1;
  }
  return {
    lines: lines.length,
    line: (n) => ({ from: starts[n - 1], to: starts[n - 1] + lines[n - 1].length, text: lines[n - 1] }),
  };
}

function diag(fields: Partial<Diagnostic>): Diagnostic {
  return { severity: "syntax", code: "X", message: "", line: 1, col: 0, end_line: null, end_col: null, data: {}, ...fields };
}

const SOURCE = "scores = [1]\nif len(scores) > 2\n    print(x)\n";

describe("diagnosticRange", () => {
  it("uses the end position when Python gives one", () => {
    // `print(totl)`: the name is at columns 6 to 10 of line 3.
    const text = "a = 1\nb = 2\nprint(totl)";
    expect(diagnosticRange(doc(text), diag({ line: 3, col: 6, end_line: 3, end_col: 10 }))).toEqual({ from: 18, to: 22 });
  });

  it("underlines the last character when Python points past the end of the line", () => {
    // "expected ':'" points at column 18, just after `if len(scores) > 2`.
    const range = diagnosticRange(doc(SOURCE), diag({ line: 2, col: 18 }));
    expect(SOURCE.slice(range.from, range.to)).toBe("2");
  });

  it("underlines the code, not the comment, when Python points at a comment", () => {
    // Python 3.14 reports "expected ':'" here at columns 19 to 20: the `#`.
    const text = "for n in range(3)  # count";
    const range = diagnosticRange(doc(text), diag({ line: 1, col: 19, end_line: 1, end_col: 20 }));
    expect(text.slice(range.from, range.to)).toBe(")");
  });

  it("underlines the word at the position when there is no end", () => {
    const range = diagnosticRange(doc(SOURCE), diag({ line: 3, col: 4 }));
    expect(SOURCE.slice(range.from, range.to)).toBe("print");
  });

  it("clamps positions that are out of range", () => {
    const range = diagnosticRange(doc("x = 1"), diag({ line: 9, col: 99 }));
    expect(range).toEqual({ from: 4, to: 5 });
  });
});
