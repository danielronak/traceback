// The shapes the Python engine's to_dict() methods produce. Keep in sync with
// engine/src/pymentor/facts.py, engine.py and exercises.py (they are a contract).

export type Severity = "syntax" | "runtime" | "style" | "logic";

export interface Diagnostic {
  severity: Severity;
  code: string;
  message: string;
  line: number; // 1-based
  col: number; // 0-based
  end_line: number | null;
  end_col: number | null; // exclusive
  data: Record<string, unknown>;
}

export interface Quiz {
  question: string;
  choices: string[];
  answer: number; // index into choices
  explain: string;
}

export interface Card {
  id: string;
  title: string;
  rule: string;
  why: string;
  hints: string[];
  exceptions: string;
  related: string[];
  quiz: Quiz | null;
}

export interface Fix {
  source: string; // the whole program after the fix
  before: string;
  after: string;
  line: number;
}

export interface Finding {
  diagnostic: Diagnostic;
  card: Card | null;
  fix: Fix | null;
  confidence: "high" | "low";
}

export interface Report {
  findings: Finding[];
  ran: boolean;
  stdout: string;
  inputs_used: string[];
  stopped: boolean;
}

export interface ExerciseTestInfo {
  name: string;
  kind: "call" | "output";
  call: string | null;
  expect: string | null;
  inputs: string[];
  output: string | null;
}

export interface Exercise {
  id: string;
  title: string;
  prompt: string;
  starter: string;
  hints: string[];
  tests: ExerciseTestInfo[];
}

export interface TestResult {
  test: ExerciseTestInfo;
  passed: boolean;
  actual: string | null;
  error: Diagnostic | null;
}

export interface ExerciseReport {
  passed: boolean;
  findings: Finding[];
  results: TestResult[];
}

export interface LessonPart {
  kind: "markdown" | "code";
  text?: string; // markdown
  code?: string; // code
  inputs?: string[];
  broken?: string | null; // the card a deliberate mistake should trigger
}

export interface Lesson {
  id: string;
  title: string;
  teaches: string[];
  parts: LessonPart[];
}

export interface CourseItem {
  kind: "lesson" | "exercise";
  id: string;
  title: string;
}

export interface Unit {
  id: string;
  title: string;
  items: CourseItem[];
}

export interface Course {
  title: string;
  units: Unit[];
  lessons: Record<string, Lesson>;
}
