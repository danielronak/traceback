// An exercise's task and its test results.

import { marked } from "marked";
import { useMemo } from "preact/hooks";
import type { Exercise, TestResult } from "../engine/types";

interface Props {
  exercise: Exercise;
  results: TestResult[] | null;
  passed: boolean;
}

export function ExercisePanel({ exercise, results, passed }: Props) {
  // Prompts come from our own curriculum files, not from users.
  const prompt = useMemo(() => marked.parse(exercise.prompt, { async: false }) as string, [exercise]);
  return (
    <section class="exercise" aria-label="Exercise">
      <h2>{exercise.title}</h2>
      <div class="prompt" dangerouslySetInnerHTML={{ __html: prompt }} />
      <h3>Tests</h3>
      <ul class="tests">
        {exercise.tests.map((test, i) => {
          const result = results?.[i];
          const status = !result ? "untested" : result.passed ? "pass" : "fail";
          return (
            <li key={i} class={`test test-${status}`}>
              <span class="test-mark" aria-label={status}>
                {status === "pass" ? "✓" : status === "fail" ? "✗" : "•"}
              </span>
              <span class="test-label">
                {test.kind === "call" ? (
                  <>
                    <code>{test.call}</code> returns <code>{test.expect}</code>
                  </>
                ) : (
                  <>
                    prints <code>{JSON.stringify(test.output)}</code>
                    {test.inputs.length > 0 && <> for input <code>{test.inputs.join(", ")}</code></>}
                  </>
                )}
                {result && !result.passed && (
                  <span class="test-actual">
                    {result.error
                      ? ` (crashed: ${result.error.code})`
                      : test.kind === "output"
                        ? ` (got ${JSON.stringify((result.actual ?? "").trimEnd())})`
                        : ` (got ${result.actual})`}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      {passed && <p class="passed" role="status">All tests pass. Well done!</p>}
    </section>
  );
}
