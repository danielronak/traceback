import { EMPTY, type KeyValueStore, type Progress } from "./store";
import { useStored } from "./useStored";

/** The learner's progress, loaded once and saved on every change. */
export function useProgress(store: KeyValueStore) {
  return useStored<Progress>(store, "progress", EMPTY, (saved, now) => ({
    lessons: { ...saved.lessons, ...now.lessons },
    exercises: { ...saved.exercises, ...now.exercises },
    mistakes: { ...saved.mistakes, ...now.mistakes },
  }));
}
