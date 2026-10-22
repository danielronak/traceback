import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { CardList } from "./cards/CardList";
import type { CardState } from "./cards/ladder";
import { Console } from "./console/Console";
import { CourseNav } from "./course/CourseNav";
import { CURRICULUM_FILES } from "./course/curriculum";
import { LessonView, type SnippetRunner } from "./course/LessonView";
import { type ItemRef, nextItem } from "./course/order";
import { Overview } from "./course/Overview";
import { Editor } from "./editor/Editor";
import { findingKey } from "./editor/positions";
import { EngineClient, EngineRestarted, type ReadyInfo, type RunHandlers } from "./engine/client";
import type { CourseItem, Finding, Report, TestResult } from "./engine/types";
import { ExercisePanel } from "./exercises/ExercisePanel";
import { explanationReported, type Feedback, NO_FEEDBACK, unknownErrorsSeen } from "./progress/feedback";
import {
  EMPTY,
  exerciseAttempted,
  KeyValueStore,
  lessonRead,
  mistakesSeen,
  newMistakes,
  practiceDue,
  practised,
} from "./progress/store";
import { useProgress } from "./progress/useProgress";
import { useStored } from "./progress/useStored";
import { loadSettings, saveSettings, type Settings } from "./settings/settings";
import { SettingsDialog } from "./settings/SettingsDialog";
import { FRESH } from "./cards/ladder";
import { load, save } from "./storage";

// The design doc's mockup: a syntax error on line 2 and a style hint on line 4.
const WELCOME = `scores = [72, 85, 90]
if len(scores) > 2
    print("Enough scores")
Total = sum(scores)
`;
const CHECK_DELAY_MS = 600; // "gentle live checking": only once typing pauses

type Mode = { kind: "playground" } | { kind: "course"; item: ItemRef | null };

function savedMode(): Mode {
  const saved = load<Mode | { kind: "exercise"; id: string }>("mode");
  if (saved?.kind === "exercise") return { kind: "course", item: { kind: "exercise", id: saved.id } }; // from M3
  return saved ?? { kind: "course", item: null };
}

export function App() {
  const engine = useMemo(() => new EngineClient(CURRICULUM_FILES), []);
  const store = useMemo(() => new KeyValueStore(), []);
  const [progress, updateProgress] = useProgress(store);
  const [feedback, updateFeedback] = useStored<Feedback>(store, "feedback", NO_FEEDBACK, (saved, now) => ({
    unknown: [...saved.unknown, ...now.unknown],
    reports: [...saved.reports, ...now.reports],
  }));
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [ready, setReady] = useState<ReadyInfo | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>(savedMode);
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
  const busy = useRef(false); // a run, test run or snippet run owns the worker
  const engineReady = useRef(false);
  const seenMistakes = useRef(new Set<string>()); // mistakes in the last run of this code

  useEffect(() => {
    engine.ready.then(
      (info) => {
        engineReady.current = true;
        setReady(info);
        const item = currentExercise(modeRef.current);
        if (item && load<string>(draftKey(modeRef.current)) === null) {
          const starter = info.exercises.find((e) => e.id === item.id)?.starter;
          if (starter !== undefined) replaceDoc(starter);
        }
      },
      (error: Error) => setFailure(error.message),
    );
  }, [engine]);

  const course = ready?.course;
  const item = mode.kind === "course" ? mode.item : null;
  const exercise = item?.kind === "exercise" ? ready?.exercises.find((e) => e.id === item.id) : undefined;
  const lesson = item?.kind === "lesson" ? course?.lessons[item.id] : undefined;
  const findings = runFindings ?? staticFindings;
  const hasEditor = mode.kind === "playground" || !!exercise;

  useEffect(() => {
    if (lesson) updateProgress((p) => lessonRead(p, lesson.id));
  }, [lesson?.id]);

  // --- live checking -----------------------------------------------------------

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

  /**
   * Count mistakes from deliberate runs only (Run, Run tests), not from live
   * checks: a half-typed line isn't a mistake yet. A mistake still on screen
   * from the last run doesn't count again.
   */
  function recordMistakes(report: { findings: Finding[] }) {
    updateFeedback((f) => unknownErrorsSeen(f, report.findings, source.current));
    const current = report.findings
      .filter((f) => f.card)
      .map((f) => ({ card: f.card!.id, key: findingKey(f.diagnostic) }));
    const fresh = newMistakes(seenMistakes.current, current);
    seenMistakes.current = new Set(current.map((m) => m.key));
    updateProgress((p) => mistakesSeen(p, fresh));
  }

  // --- running -------------------------------------------------------------------

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

  /** Every use of the worker goes through here, so only one runs at a time. */
  async function exclusive<T>(work: () => Promise<T>): Promise<T> {
    if (!engineReady.current || busy.current) throw new Error("Python is busy.");
    window.clearTimeout(checkTimer.current);
    busy.current = true;
    setRunning(true);
    try {
      return await work();
    } finally {
      busy.current = false;
      setRunning(false);
      setWaiting(false);
      check(); // anything typed meanwhile
    }
  }

  async function run() {
    setOutput("");
    setNote(null);
    try {
      const report = await exclusive(() =>
        engine.run(source.current, {
          onOutput: appendOutput,
          onInputRequest: () => setWaiting(true),
          onInputUnavailable: () =>
            setNote("This browser session can't read input(); open PyMentor from its own address to enable it."),
        }),
      );
      flushOutput(); // the program's last words before the closing note
      setRunFindings(report.findings);
      setSelected(0);
      recordMistakes(report);
      const crash = report.findings.find((f) => f.diagnostic.severity === "runtime");
      setNote(
        report.stopped
          ? "Stopped."
          : !report.ran
            ? "Python couldn't run this. See the card."
            : crash
              ? "The program crashed. See the card."
              : "The program finished.",
      );
    } catch (error) {
      flushOutput();
      setNote(error instanceof EngineRestarted ? error.message : `Something went wrong: ${error}`);
    }
  }

  async function runTests() {
    if (!exercise) return;
    setNote(null);
    try {
      const report = await exclusive(() => engine.runExercise(exercise.id, source.current));
      setResults(report.results);
      setPassed(report.passed);
      setRunFindings(report.findings);
      setSelected(0);
      recordMistakes(report);
      updateProgress((p) => exerciseAttempted(p, exercise.id, report.passed));
    } catch (error) {
      setNote(error instanceof EngineRestarted ? error.message : `Something went wrong: ${error}`);
    }
  }

  const snippetRunner: SnippetRunner = {
    ready: !!ready && !running,
    run: (code: string, handlers: RunHandlers): Promise<Report> => exclusive(() => engine.run(code, handlers)),
    answer: (text) => engine.answer(text),
    stop: () => engine.stop(),
  };

  // --- navigation ------------------------------------------------------------------

  function switchMode(next: Mode) {
    save("mode", next);
    modeRef.current = next;
    setMode(next);
    seenMistakes.current = new Set();
    setOutput("");
    setNote(null);
    const starter =
      next.kind === "playground"
        ? WELCOME
        : next.item?.kind === "exercise"
          ? ready?.exercises.find((e) => e.id === next.item!.id)?.starter
          : undefined;
    if (starter !== undefined) replaceDoc(load<string>(draftKey(next)) ?? starter);
    window.scrollTo({ top: 0 });
  }

  const open = (target: ItemRef | null) => switchMode({ kind: "course", item: target });
  const nextLink = (from: ItemRef): { title: string; open(): void } | null => {
    const next: CourseItem | undefined = course && nextItem(course, from);
    return next ? { title: next.title, open: () => open(next) } : null;
  };

  function tryInPlayground(code: string) {
    switchMode({ kind: "playground" });
    replaceDoc(code);
  }

  const layout = !course || mode.kind === "playground" ? "" : hasEditor ? "with-nav" : "with-nav reading";

  return (
    <div class="app">
      <header class="topbar">
        <h1 class="brand">PyMentor</h1>
        <nav class="modes" aria-label="Mode">
          <button
            type="button"
            aria-pressed={mode.kind === "course"}
            disabled={!ready}
            onClick={() => switchMode({ kind: "course", item: mode.kind === "course" ? mode.item : null })}
          >
            Course
          </button>
          <button
            type="button"
            aria-pressed={mode.kind === "playground"}
            onClick={() => switchMode({ kind: "playground" })}
          >
            Playground
          </button>
        </nav>
        <button type="button" class="settings-button" onClick={() => setSettingsOpen(true)}>
          Settings
        </button>
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

      <SettingsDialog
        open={settingsOpen}
        settings={settings}
        feedback={feedback}
        pythonVersion={ready?.pythonVersion ?? "unknown"}
        onChange={(next) => {
          setSettings(next);
          saveSettings(next);
        }}
        onClearProgress={() => {
          updateProgress(() => EMPTY);
          updateFeedback(() => NO_FEEDBACK);
          setCardStates({});
        }}
        onClose={() => setSettingsOpen(false)}
      />

      <main class={`layout ${layout}`}>
        {course && mode.kind === "course" && (
          <CourseNav course={course} progress={progress} current={item} onOpen={open} />
        )}

        {course && mode.kind === "course" && !item && (
          <Overview course={course} progress={progress} onOpen={open} />
        )}

        {lesson && item && (
          <LessonView
            lesson={lesson}
            runner={snippetRunner}
            next={nextLink(item)}
            onTryInPlayground={tryInPlayground}
          />
        )}

        {!course && mode.kind === "course" && (
          <p class="loading" role="status">
            Loading Python and the course…
          </p>
        )}

        {hasEditor && (
          <>
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
                    <button type="button" disabled={running} onClick={() => replaceDoc(exercise.starter)}>
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
              <p class="editor-tip muted">Tip: press Escape, then Tab, to move on from the editor.</p>
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
              {exercise && item && (
                <ExercisePanel exercise={exercise} results={results} passed={passed} next={nextLink(item)} />
              )}
              <CardList
                findings={findings}
                selected={selected}
                states={cardStates}
                onSelect={setSelected}
                onState={(key, state) => setCardStates((all) => ({ ...all, [key]: state }))}
                onAcceptFix={(finding) => finding.fix && replaceDoc(finding.fix.source)}
                emptyMessage={ready ? "No problems found so far." : "Loading Python…"}
                practiceDue={(cardId) => practiceDue(progress, cardId)}
                onPractised={(cardId) => updateProgress((p) => practised(p, cardId))}
                initial={settings.showFixes ? { ...FRESH, fix: true } : FRESH}
                onReport={(finding, reason, text) =>
                  updateFeedback((f) => explanationReported(f, finding, reason, text, source.current))
                }
              />
            </aside>
          </>
        )}
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

function currentExercise(mode: Mode): ItemRef | null {
  return mode.kind === "course" && mode.item?.kind === "exercise" ? mode.item : null;
}

function draftKey(mode: Mode): string {
  const item = currentExercise(mode);
  return item ? `draft:${item.id}` : "draft:playground";
}
