// A lesson: Markdown text with runnable snippets.

import { Marked } from "marked";
import { useMemo, useState } from "preact/hooks";
import { CardList } from "../cards/CardList";
import type { CardState } from "../cards/ladder";
import { Console } from "../console/Console";
import { EngineRestarted, type RunHandlers } from "../engine/client";
import type { Finding, Lesson, LessonPart, Report } from "../engine/types";
import { Highlighted } from "./highlight";

export interface SnippetRunner {
  run(code: string, handlers: RunHandlers): Promise<Report>;
  answer(text: string): void;
  stop(): void;
  ready: boolean;
}

interface Props {
  lesson: Lesson;
  runner: SnippetRunner;
  next: { title: string; open(): void } | null;
  onTryInPlayground(code: string): void;
}

export function LessonView({ lesson, runner, next, onTryInPlayground }: Props) {
  return (
    <article class="lesson" aria-labelledby="lesson-title">
      <h2 id="lesson-title">{lesson.title}</h2>
      {lesson.parts.map((part, index) =>
        part.kind === "markdown" ? (
          <Markdown key={index} text={part.text ?? ""} />
        ) : (
          <Snippet key={`${lesson.id}:${index}`} part={part} runner={runner} onTryInPlayground={onTryInPlayground} />
        ),
      )}
      {next && (
        <p class="lesson-next">
          <button type="button" class="primary" onClick={next.open}>
            Next: {next.title}
          </button>
        </p>
      )}
    </article>
  );
}

// Lesson sections are written as `##`; the lesson title is the page's h2, so
// sections render one level below it.
const lessonMarkdown = new Marked({
  walkTokens(token) {
    if (token.type === "heading") token.depth = Math.min(token.depth + 1, 6);
  },
});

function Markdown({ text }: { text: string }) {
  // Lessons come from our own curriculum files, not from users.
  const html = useMemo(() => lessonMarkdown.parse(text, { async: false }) as string, [text]);
  return <div class="prose" dangerouslySetInnerHTML={{ __html: html }} />;
}

function Snippet({
  part,
  runner,
  onTryInPlayground,
}: {
  part: LessonPart;
  runner: SnippetRunner;
  onTryInPlayground(code: string): void;
}) {
  const code = part.code ?? "";
  const [ran, setRan] = useState(false);
  const [output, setOutput] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selected, setSelected] = useState(0);
  const [states, setStates] = useState<Record<string, CardState>>({});

  async function run() {
    setRan(true);
    setRunning(true);
    setOutput("");
    setNote(null);
    setFindings([]);
    let text = "";
    try {
      const report = await runner.run(code, {
        onOutput: (chunk) => {
          text += chunk;
          setOutput(text);
        },
        onInputRequest: () => setWaiting(true),
        onInputUnavailable: () => setNote("This browser session can't read input()."),
      });
      setFindings(report.findings);
      setSelected(0);
      const blocking = report.findings.find((f) => f.diagnostic.severity === "syntax" || f.diagnostic.severity === "runtime");
      setNote(
        report.stopped
          ? "Stopped."
          : blocking?.diagnostic.severity === "syntax"
            ? "Python couldn't run this. See the card below."
            : blocking
              ? "The program crashed. See the card below."
              : "The program finished.",
      );
    } catch (error) {
      setNote(error instanceof EngineRestarted ? error.message : String(error));
    } finally {
      setRunning(false);
      setWaiting(false);
    }
  }

  return (
    <figure class={`snippet ${part.broken ? "broken" : ""}`}>
      {part.broken && (
        <figcaption>This one has a mistake on purpose. Run it to see how it's explained.</figcaption>
      )}
      <pre class="snippet-code">
        <code>
          <Highlighted code={code} />
        </code>
      </pre>
      <div class="snippet-actions">
        <button type="button" class="primary" disabled={!runner.ready || running} onClick={run}>
          Run
        </button>
        <button type="button" onClick={() => onTryInPlayground(code)}>
          Try it in the playground
        </button>
      </div>
      {ran && (
        <Console
          output={output}
          waiting={waiting}
          running={running}
          note={note}
          onAnswer={(text) => {
            setWaiting(false);
            runner.answer(text);
          }}
          onStop={runner.stop}
        />
      )}
      {findings.length > 0 && (
        <CardList
          findings={findings}
          selected={selected}
          states={states}
          onSelect={setSelected}
          onState={(key, state) => setStates((all) => ({ ...all, [key]: state }))}
          onAcceptFix={(finding) => finding.fix && onTryInPlayground(finding.fix.source)}
          acceptLabel="Open the fix in the playground"
          emptyMessage=""
        />
      )}
    </figure>
  );
}
