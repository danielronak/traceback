import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { CardList } from "./cards/CardList";
import type { CardState } from "./cards/ladder";
import { Console } from "./console/Console";
import { Editor } from "./editor/Editor";
import { EngineClient, EngineRestarted, type ReadyInfo } from "./engine/client";
import type { Exercise, Finding, TestResult } from "./engine/types";
import { EXERCISE_FILES } from "./exercises/curriculum";
import { ExercisePanel } from "./exercises/ExercisePanel";
import { load, save } from "./storage";

// The design doc's mockup: a syntax error on line 2 and a style hint on line 4.
const WELCOME = `scores = [72, 85, 90]
if len(scores) > 2
    print("Enough scores")
Total = sum(scores)
`;
const CHECK_DELAY_MS = 600; // "gentle live checking": only once typing pauses

type Mode = { kind: "playground" } | { kind: "exercise"; id: string };

export function App() {
  const engine = useMemo(() => new EngineClient(EXERCISE_FILES), []);
  const [ready, setReady] = useState<ReadyInfo | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>(() => load<Mode>("mode") ?? { kind: "playground" });
  const modeRef = useRef(mode); // read by callbacks that outlive a render

  const [doc, setDoc] = useState(() => load<string>(draftKey(mode)) ?? WELCOME);
  const [docVersion, setDocVersion] = useState(0);
  const source = useRef(doc);

  const [staticFindings, setStaticFindings] = useState<Finding[]>([]);
  const [runFindings, setRunFindings] = useState<Finding[] | null>(null);
  const [selected, setSelected] = useState(0);
  const [cardStates, setCardStates] = useState<Record<string, CardState>>({});

  const [output, setOutput] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [results, setResults] = useState<TestResult[] | null>(null);
  const [passed, setPassed] = useState(false);

  const checkTimer = useRef<number>();
  const checkSeq = useRef(0);
  const dirty = useRef(true);
  const busy = useRef(false); // a run or test run owns the worker
  const engineReady = useRef(false);

  useEffect(() => {
    engine.ready.then(
      (info) => {
        engineReady.current = true;
        setReady(info);
        const current = modeRef.current;
        if (current.kind === "exercise" && load<string>(draftKey(current)) === null) {
          const starter = info.exercises.find((e) => e.id === current.id)?.starter;
          if (starter !== undefined) replaceDoc(starter);
        }
      },
      (error: Error) => setFailure(error.message),
    );
  }, [engine]);

  const exercises = ready?.exercises ?? [];
  const exercise = mode.kind === "exercise" ? exercises.find((e) => e.id === mode.id) : undefined;
  const findings = runFindings ?? staticFindings;

  async function check() {
    if (!engineReady.current || busy.current || !dirty.current) return;
    dirty.current = false;
    const seq = ++checkSeq.current;
    const report = await engine.check(source.current);
    if (seq === checkSeq.current) setStaticFindings(report.findings);
  }

  useEffect(() => {
    dirty.current = true;
    check();
  }, [ready]);

  function onChange(text: string) {
    source.current = text;
    dirty.current = true;
    save(draftKey(modeRef.current), text);
    setRunFindings(null); // their positions may no longer be true
    setResults(null);
    setPassed(false);
    window.clearTimeout(checkTimer.current);
    checkTimer.current = window.setTimeout(check, CHECK_DELAY_MS);
  }

  function replaceDoc(text: string) {
    source.current = text;
    setDoc(text);
    setDocVersion((v) => v + 1);
    onChange(text);
  }

  // Render streamed output at most once per frame.
  const outputBuffer = useRef("");
  const outputFrame = useRef(0);
  function appendOutput(text: string) {
    outputBuffer.current += text;
    if (!outputFrame.current) outputFrame.current = requestAnimationFrame(flushOutput);
  }
  function flushOutput() {
    cancelAnimationFrame(outputFrame.current);
    outputFrame.current = 0;
    const chunk = outputBuffer.current;
    outputBuffer.current = "";
    if (chunk) setOutput((previous) => previous + chunk);
  }

  async function run() {
    if (!engineReady.current || busy.current) return;
    window.clearTimeout(checkTimer.current);
    busy.current = true;
    setRunning(true);
    setOutput("");
    setNote(null);
    try {
      const report = await engine.run(source.current, {
        onOutput: appendOutput,
        onInputRequest: () => setWaiting(true),
        onInputUnavailable: () =>
          setNote("This browser session can't read input(); open PyMentor from its own address to enable it."),
      });
      flushOutput(); // the program's last words before the closing note
      setRunFindings(report.findings);
      setSelected(0);
      const crash = report.findings.find((f) => f.diagnostic.severity === "runtime");
      setNote(report.stopped ? "Stopped." : crash ? "The program crashed. See the card." : "The program finished.");
    } catch (error) {
      flushOutput();
      setNote(error instanceof EngineRestarted ? error.message : `Something went wrong: ${error}`);
    } finally {
      busy.current = false;
      setRunning(false);
      setWaiting(false);
      check(); // anything typed during the run
    }
  }

  async function runTests() {
    if (!engineReady.current || busy.current || !exercise) return;
    window.clearTimeout(checkTimer.current);
    busy.current = true;
    setRunning(true);
    setNote(null);
    try {
      const report = await engine.runExercise(exercise.id, source.current);
      setResults(report.results);
      setPassed(report.passed);
      setRunFindings(report.findings);
      setSelected(0);
    } catch (error) {
      setNote(error instanceof EngineRestarted ? error.message : `Something went wrong: ${error}`);
    } finally {
      busy.current = false;
      setRunning(false);
      check();
    }
  }

  function switchMode(next: Mode) {
    save("mode", next);
    modeRef.current = next;
    setMode(next);
    const starter = next.kind === "exercise" ? exercises.find((e) => e.id === next.id)?.starter : WELCOME;
    replaceDoc(load<string>(draftKey(next)) ?? starter ?? "");
    setOutput("");
    setNote(null);
  }

  function resetExercise(e: Exercise) {
    replaceDoc(e.starter);
  }

  return (
    <div class="app">
      <header class="topbar">
        <h1 class="brand">PyMentor</h1>
        <nav class="modes" aria-label="Mode">
          <button
            type="button"
            aria-pressed={mode.kind === "playground"}
            onClick={() => switchMode({ kind: "playground" })}
          >
            Playground
          </button>
          <button
            type="button"
            aria-pressed={mode.kind === "exercise"}
            disabled={!ready}
            onClick={() => switchMode({ kind: "exercise", id: exercise?.id ?? exercises[0].id })}
          >
            Exercises
          </button>
        </nav>
        <span class={`status ${ready ? "ok" : failure ? "bad" : ""}`} role="status">
          {failure ? (
            "Python failed to load"
          ) : ready ? (
            <>
              <span class="wide-only">Python </span>
              {ready.pythonVersion} ready
            </>
          ) : (
            "Loading Python…"
          )}
        </span>
      </header>

      {failure && <p class="banner bad">{failure}</p>}

      <main class={`layout ${exercise ? "with-exercises" : ""}`}>
        {exercise && (
          <nav class="exercise-list" aria-label="Exercises">
            <ol>
              {exercises.map((e) => (
                <li key={e.id}>
                  <button
                    type="button"
                    aria-current={e.id === exercise.id}
                    onClick={() => switchMode({ kind: "exercise", id: e.id })}
                  >
                    {e.title}
                  </button>
                </li>
              ))}
            </ol>
          </nav>
        )}

        <section class="workspace">
          <div class="toolbar">
            <button type="button" class="primary" disabled={!ready || running} onClick={run}>
              Run
            </button>
            {exercise && (
              <>
                <button type="button" class="primary" disabled={!ready || running} onClick={runTests}>
                  Run tests
                </button>
                <button type="button" disabled={running} onClick={() => resetExercise(exercise)}>
                  Start over
                </button>
              </>
            )}
            <Legend />
          </div>
          <Editor
            doc={doc}
            version={docVersion}
            findings={findings}
            onChange={onChange}
            onLineLeave={check}
            onSelectFinding={setSelected}
            label="Python code editor"
          />
          <Console
            output={output}
            waiting={waiting}
            running={running}
            note={note}
            onAnswer={(text) => {
              setWaiting(false);
              engine.answer(text);
            }}
            onStop={() => engine.stop()}
          />
        </section>

        <aside class="side">
          {exercise && <ExercisePanel exercise={exercise} results={results} passed={passed} />}
          <CardList
            findings={findings}
            selected={selected}
            states={cardStates}
            onSelect={setSelected}
            onState={(key, state) => setCardStates((all) => ({ ...all, [key]: state }))}
            onAcceptFix={(finding) => finding.fix && replaceDoc(finding.fix.source)}
            emptyMessage={ready ? "No problems found so far." : "Loading Python…"}
          />
        </aside>
      </main>
    </div>
  );
}

function Legend() {
  return (
    <p class="legend" aria-label="Colour key">
      <span class="key key-syntax">Won't run</span>
      <span class="key key-runtime">Crashed</span>
      <span class="key key-logic">Wrong answer</span>
      <span class="key key-style">Style</span>
    </p>
  );
}

function draftKey(mode: Mode): string {
  return mode.kind === "exercise" ? `draft:${mode.id}` : "draft:playground";
}
