// The course contents, with what's done ticked off.

import { useState } from "preact/hooks";
import type { Course } from "../engine/types";
import type { Progress } from "../progress/store";
import { isDone, type ItemRef, sameItem } from "./order";

interface Props {
  course: Course;
  progress: Progress;
  current: ItemRef | null; // null: the overview
  onOpen(item: ItemRef | null): void;
}

export function CourseNav({ course, progress, current, onOpen }: Props) {
  const [open, setOpen] = useState(false); // on narrow screens the list folds away
  const here = current
    ? course.units.flatMap((u) => u.items).find((item) => sameItem(item, current))?.title
    : "Overview";
  return (
    <nav class={`course-nav ${open ? "open" : ""}`} aria-label="Course">
      <button type="button" class="course-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        Course: {here}
      </button>
      <div class="course-contents">
        <button
          type="button"
          class="course-item"
          aria-current={current === null ? "page" : undefined}
          onClick={() => {
            setOpen(false);
            onOpen(null);
          }}
        >
          Overview
        </button>
        {course.units.map((unit) => (
          <section key={unit.id} class="course-unit">
            <h2>{unit.title}</h2>
            <ol>
              {unit.items.map((item) => {
                const done = isDone(progress, item);
                return (
                  <li key={`${item.kind}:${item.id}`}>
                    <button
                      type="button"
                      class={`course-item ${item.kind}`}
                      aria-current={sameItem(item, current) ? "page" : undefined}
                      onClick={() => {
                        setOpen(false);
                        onOpen(item);
                      }}
                    >
                      <span class={`mark ${done ? "done" : ""}`} aria-hidden="true">
                        {done ? "✓" : item.kind === "lesson" ? "◇" : "○"}
                      </span>
                      <span class="course-item-title">{item.title}</span>
                      <span class="visually-hidden">
                        {item.kind === "lesson" ? ", lesson" : ", exercise"}
                        {done ? ", done" : ""}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </div>
    </nav>
  );
}
