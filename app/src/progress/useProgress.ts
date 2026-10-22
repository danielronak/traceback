import { useEffect, useRef, useState } from "preact/hooks";
import { EMPTY, KeyValueStore, type Progress } from "./store";

const KEY = "progress";

/** The learner's progress, loaded once and saved on every change. */
export function useProgress(store: KeyValueStore) {
  const [progress, setProgress] = useState<Progress>(EMPTY);
  const current = useRef(progress);

  useEffect(() => {
    store.get<Progress>(KEY).then((saved) => {
      if (!saved) return;
      // Merge, in case anything was recorded before the saved copy arrived.
      const merged: Progress = {
        lessons: { ...saved.lessons, ...current.current.lessons },
        exercises: { ...saved.exercises, ...current.current.exercises },
        mistakes: { ...saved.mistakes, ...current.current.mistakes },
      };
      current.current = merged;
      setProgress(merged);
    });
  }, [store]);

  function update(change: (progress: Progress) => Progress) {
    const next = change(current.current);
    if (next === current.current) return;
    current.current = next;
    setProgress(next);
    store.set(KEY, next);
  }

  return [progress, update] as const;
}
