// Course navigation and the study plan, as pure functions of course and progress.

import type { Course, CourseItem } from "../engine/types";
import type { Progress } from "../progress/store";

export type ItemRef = Pick<CourseItem, "kind" | "id">;

export function allItems(course: Course): CourseItem[] {
  return course.units.flatMap((unit) => unit.items);
}

export function sameItem(a: ItemRef | null | undefined, b: ItemRef | null | undefined): boolean {
  return !!a && !!b && a.kind === b.kind && a.id === b.id;
}

export function isDone(progress: Progress, item: ItemRef): boolean {
  return item.kind === "lesson" ? !!progress.lessons[item.id] : !!progress.exercises[item.id]?.passedAt;
}

export function nextItem(course: Course, item: ItemRef): CourseItem | undefined {
  const items = allItems(course);
  const index = items.findIndex((i) => sameItem(i, item));
  return index >= 0 ? items[index + 1] : undefined;
}

/** Where to continue: the first item not done yet. */
export function firstIncomplete(course: Course, progress: Progress): CourseItem | undefined {
  return allItems(course).find((item) => !isDone(progress, item));
}

export interface WeakSpot {
  lesson: CourseItem;
  mistakes: number;
}

/**
 * Lessons worth revisiting: those whose cards (their `teaches` list) the
 * learner has run into most often.
 */
export function weakSpots(course: Course, progress: Progress, limit = 3): WeakSpot[] {
  const lessons = allItems(course).filter((item) => item.kind === "lesson");
  return lessons
    .map((lesson) => ({
      lesson,
      mistakes: course.lessons[lesson.id].teaches.reduce((sum, card) => sum + (progress.mistakes[card]?.count ?? 0), 0),
    }))
    .filter((spot) => spot.mistakes > 0)
    .sort((a, b) => b.mistakes - a.mistakes)
    .slice(0, limit);
}
