// Settings: teaching preference, the learner's feedback, and clearing progress.

import { useEffect, useRef, useState } from "preact/hooks";
import { exportFeedback, type Feedback } from "../progress/feedback";
import type { Settings } from "./settings";

interface Props {
  open: boolean;
  settings: Settings;
  feedback: Feedback;
  pythonVersion: string;
  onChange(settings: Settings): void;
  onClearProgress(): void;
  onClose(): void;
}

export function SettingsDialog({ open, settings, feedback, pythonVersion, onChange, onClearProgress, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [includeCode, setIncludeCode] = useState(false);

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  function download() {
    const data = exportFeedback(feedback, includeCode, pythonVersion);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `pymentor-feedback-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  const unknown = feedback.unknown.length;
  const reports = feedback.reports.length;
  return (
    <dialog ref={dialog} class="settings" aria-labelledby="settings-title" onClose={onClose}>
      <h2 id="settings-title">Settings</h2>

      <section>
        <h3>Teaching</h3>
        <label class="check">
          <input
            type="checkbox"
            checked={settings.showFixes}
            onChange={(event) => onChange({ ...settings, showFixes: (event.target as HTMLInputElement).checked })}
          />
          Show the fix straight away, instead of hints first
        </label>
        <p class="muted">Handy for teachers demonstrating, or for reviewing. Learning sticks better when you try first.</p>
      </section>

      <section>
        <h3>Help improve PyMentor</h3>
        <p>
          On this device only, PyMentor keeps a note of errors it has no lesson for yet ({unknown}) and explanations you
          reported ({reports}). Nothing is ever sent anywhere. You can download them to share with the people who make
          PyMentor.
        </p>
        <label class="check">
          <input
            type="checkbox"
            checked={includeCode}
            onChange={(event) => setIncludeCode((event.target as HTMLInputElement).checked)}
          />
          Include the line of code each one came from
        </label>
        <p>
          <button type="button" disabled={unknown + reports === 0} onClick={download}>
            Download feedback
          </button>
        </p>
      </section>

      <section>
        <h3>Keyboard</h3>
        <p class="muted">In the editor, Tab indents your code. To move on from the editor, press Escape, then Tab.</p>
      </section>

      <section>
        <h3>Your progress</h3>
        <p>
          <button
            type="button"
            class="danger"
            onClick={() => {
              if (confirm("Clear your progress and feedback on this device? This can't be undone.")) onClearProgress();
            }}
          >
            Clear my progress
          </button>
        </p>
      </section>

      <form method="dialog" class="settings-close">
        <button type="submit" class="primary">
          Done
        </button>
      </form>
    </dialog>
  );
}
