// The program's console: its output, and a box to answer input().

import { useEffect, useRef, useState } from "preact/hooks";

interface Props {
  output: string;
  waiting: boolean; // the program is waiting for input()
  running: boolean;
  note: string | null; // a status line, e.g. "Stopped."
  onAnswer(text: string): void;
  onStop(): void;
}

export function Console({ output, waiting, running, note, onAnswer, onStop }: Props) {
  const [answer, setAnswer] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const log = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (waiting) input.current?.focus();
  }, [waiting]);
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [output, note]);

  return (
    <section class="console" aria-label="Program output">
      <div class="console-head">
        <span>Output</span>
        {running && (
          <button type="button" class="stop" onClick={onStop}>
            Stop
          </button>
        )}
      </div>
      <pre class="console-log" ref={log} aria-live="polite">
        {output}
        {note && <span class="console-note">{note}</span>}
        {!output && !note && !running && <span class="console-placeholder">Press Run to see what your program prints.</span>}
      </pre>
      {waiting && (
        <form
          class="console-input"
          onSubmit={(event) => {
            event.preventDefault();
            // Read the element itself: the last keystroke may not have re-rendered yet.
            onAnswer(input.current?.value ?? answer);
            setAnswer("");
          }}
        >
          <label for="console-answer">Your program is waiting for input:</label>
          <input
            id="console-answer"
            ref={input}
            value={answer}
            autocomplete="off"
            spellcheck={false}
            onInput={(event) => setAnswer((event.target as HTMLInputElement).value)}
          />
          <button type="submit">Enter</button>
        </form>
      )}
    </section>
  );
}
