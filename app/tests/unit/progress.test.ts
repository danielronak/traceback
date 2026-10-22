import { describe, expect, it } from "vitest";
import { firstIncomplete, nextItem, weakSpots } from "../../src/course/order";
import type { Course } from "../../src/engine/types";
import {
  EMPTY,
  exerciseAttempted,
  lessonRead,
  mistakesSeen,
  newMistakes,
  practiceDue,
  practised,
} from "../../src/progress/store";

const COURSE: Course = {
  title: "T",
  units: [
    {
      id: "u1",
      title: "One",
      items: [
        { kind: "lesson", id: "printing", title: "Printing" },
        { kind: "exercise", id: "hello", title: "Hello" },
      ],
    },
    { id: "u2", title: "Two", items: [{ kind: "lesson", id: "loops", title: "Loops" }] },
  ],
  lessons: {
    printing: { id: "printing", title: "Printing", teaches: ["name-meant-string"], parts: [] },
    loops: { id: "loops", title: "Loops", teaches: ["int-not-iterable", "infinite-loop"], parts: [] },
  },
};

describe("progress", () => {
  it("records lessons once and keeps the first pass of an exercise", () => {
    let p = lessonRead(EMPTY, "printing", 1);
    expect(lessonRead(p, "printing", 2)).toBe(p);
    p = exerciseAttempted(p, "hello", false, 3);
    p = exerciseAttempted(p, "hello", true, 4);
    p = exerciseAttempted(p, "hello", false, 5);
    expect(p.exercises.hello).toEqual({ attempts: 3, passedAt: 4 });
  });

  it("makes repetition into practice, then resets after a quiz", () => {
    let p = EMPTY;
    for (let i = 0; i < 3; i++) p = mistakesSeen(p, ["missing-colon"]);
    expect(practiceDue(p, "missing-colon")).toBe(true);
    p = practised(p, "missing-colon");
    expect(practiceDue(p, "missing-colon")).toBe(false);
    expect(p.mistakes["missing-colon"].count).toBe(3);
  });

  it("counts a mistake still on screen from the last run only once", () => {
    const previous = new Set(["a:2"]);
    expect(newMistakes(previous, [{ card: "a", key: "a:2" }, { card: "b", key: "b:5" }])).toEqual(["b"]);
  });
});

describe("the study plan", () => {
  it("continues at the first thing not done, in course order", () => {
    expect(firstIncomplete(COURSE, EMPTY)?.id).toBe("printing");
    const p = lessonRead(EMPTY, "printing");
    expect(firstIncomplete(COURSE, p)?.id).toBe("hello");
    expect(nextItem(COURSE, { kind: "exercise", id: "hello" })?.id).toBe("loops");
    expect(nextItem(COURSE, { kind: "lesson", id: "loops" })).toBeUndefined();
  });

  it("suggests the lessons that cover the most frequent mistakes", () => {
    let p = mistakesSeen(EMPTY, ["infinite-loop", "int-not-iterable", "name-meant-string"]);
    p = mistakesSeen(p, ["infinite-loop"]);
    expect(weakSpots(COURSE, p).map((s) => [s.lesson.id, s.mistakes])).toEqual([
      ["loops", 3],
      ["printing", 1],
    ]);
  });
});
