import { describe, expect, it } from "vitest";
import type { Finding } from "../../src/engine/types";
import { explanationReported, exportFeedback, NO_FEEDBACK, unknownErrorsSeen } from "../../src/progress/feedback";

const raw: Finding = {
  diagnostic: { severity: "runtime", code: "RuntimeError", message: "boom", line: 2, col: 0, end_line: null, end_col: null, data: {} },
  card: null,
  fix: null,
  confidence: "low",
};
const taught: Finding = {
  ...raw,
  card: { id: "zero-division", title: "Division by zero on line 2", rule: "", why: "", hints: [], exceptions: "", related: [], quiz: null },
  confidence: "high",
};
const SOURCE = "x = 1\nraise RuntimeError('boom')\n";

describe("feedback", () => {
  it("notes errors without a card once per kind, counting repeats", () => {
    let f = unknownErrorsSeen(NO_FEEDBACK, [raw, taught], SOURCE, 1);
    f = unknownErrorsSeen(f, [raw], SOURCE, 2);
    expect(f.unknown).toEqual([
      { code: "RuntimeError", message: "boom", severity: "runtime", count: 2, firstSeen: 1, lastSeen: 2, line: "raise RuntimeError('boom')" },
    ]);
  });

  it("leaves learner code out of the download unless they choose to include it", () => {
    let f = unknownErrorsSeen(NO_FEEDBACK, [raw], SOURCE);
    f = explanationReported(f, taught, "confusing", "  too long  ", SOURCE);
    const without = exportFeedback(f, false, "3.14");
    expect(JSON.stringify(without)).not.toContain("raise RuntimeError");
    expect(without.explanationReports[0]).toMatchObject({ cardId: "zero-division", reason: "confusing", note: "too long" });
    expect(JSON.stringify(exportFeedback(f, true, "3.14"))).toContain("raise RuntimeError");
  });
});
