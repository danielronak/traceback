// Feedback for the people who make PyMentor: errors that have no rule card
// yet, and explanations a learner reported. Kept on this device only; the
// learner can download it deliberately from Settings (principle 3). Learner
// code is left out of the download unless they choose to include it.

import type { Finding } from "../engine/types";

export interface UnknownError {
  code: string;
  message: string;
  severity: string;
  count: number;
  firstSeen: number;
  lastSeen: number;
  line: string; // the line of code involved (only exported if the learner agrees)
}

export type ReportReason = "wrong" | "confusing" | "other";

export interface ExplanationReport {
  cardId: string;
  title: string;
  reason: ReportReason;
  note: string;
  at: number;
  line: string;
}

export interface Feedback {
  unknown: UnknownError[];
  reports: ExplanationReport[];
}

export const NO_FEEDBACK: Feedback = { unknown: [], reports: [] };
const MAX_ENTRIES = 200;

function lineOf(source: string, line: number): string {
  return source.split("\n")[line - 1] ?? "";
}

/** Note the errors in a report that have no card yet, once per kind. */
export function unknownErrorsSeen(feedback: Feedback, findings: Finding[], source: string, now = Date.now()): Feedback {
  const missing = findings.filter((f) => !f.card);
  if (missing.length === 0) return feedback;
  const unknown = [...feedback.unknown];
  for (const { diagnostic: d } of missing) {
    const index = unknown.findIndex((u) => u.code === d.code && u.message === d.message);
    if (index >= 0) {
      unknown[index] = { ...unknown[index], count: unknown[index].count + 1, lastSeen: now };
    } else if (unknown.length < MAX_ENTRIES) {
      unknown.push({
        code: d.code,
        message: d.message,
        severity: d.severity,
        count: 1,
        firstSeen: now,
        lastSeen: now,
        line: lineOf(source, d.line),
      });
    }
  }
  return { ...feedback, unknown };
}

export function explanationReported(
  feedback: Feedback,
  finding: Finding,
  reason: ReportReason,
  note: string,
  source: string,
  now = Date.now(),
): Feedback {
  if (!finding.card) return feedback;
  const report: ExplanationReport = {
    cardId: finding.card.id,
    title: finding.card.title,
    reason,
    note: note.trim(),
    at: now,
    line: lineOf(source, finding.diagnostic.line),
  };
  return { ...feedback, reports: [...feedback.reports, report].slice(-MAX_ENTRIES) };
}

/** What a download contains. Code lines only when the learner ticks the box. */
export function exportFeedback(feedback: Feedback, includeCode: boolean, pythonVersion: string, now = Date.now()) {
  const strip = <T extends { line: string }>(entry: T): T | Omit<T, "line"> => {
    if (includeCode) return entry;
    const { line: _line, ...rest } = entry;
    return rest;
  };
  return {
    app: "PyMentor",
    exportedAt: new Date(now).toISOString(),
    python: pythonVersion,
    includesCode: includeCode,
    unknownErrors: feedback.unknown.map(strip),
    explanationReports: feedback.reports.map(strip),
  };
}
