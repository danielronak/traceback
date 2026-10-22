// The study plan: how far the learner has got, where to continue, and what
// to revisit.

import type { Course } from "../engine/types";
import type { Progress } from "../progress/store";
import { allItems, firstIncomplete, isDone, type ItemRef, weakSpots } from "./order";

interface Props {
  course: Course;
  progress: Progress;
  onOpen(item: ItemRef): void;
}

export function Overview({ course, progress, onOpen }: Props) {
  const items = allItems(course);
  const done = items.filter((item) => isDone(progress, item)).length;
  const next = firstIncomplete(course, progress);
  const weak = weakSpots(course, progress);
  return (
    <section class="overview" aria-labelledby="overview-title">
      <h2 id="overview-title">{course.title}</h2>
      <p class="overview-progress">
        <progress value={done} max={items.length} aria-label="Course progress" /> {done} of {items.length} done
      </p>
      {next ? (
        <button type="button" class="primary big" onClick={() => onOpen(next)}>
          {done === 0 ? "Start" : "Continue"}: {next.title}
        </button>
      ) : (
        <p class="passed">You've finished the whole course. Brilliant work!</p>
      )}

      {weak.length > 0 && (
        <section class="weak-spots">
          <h3>Practise your weak spots</h3>
          <p>These lessons cover the mistakes you've made most often. A second read helps them stick.</p>
          <ul>
            {weak.map((spot) => (
              <li key={spot.lesson.id}>
                <button type="button" onClick={() => onOpen(spot.lesson)}>
                  Revisit “{spot.lesson.title}”
                </button>{" "}
                <span class="muted">
                  {spot.mistakes} {spot.mistakes === 1 ? "mistake" : "mistakes"} it covers
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div class="overview-units">
        {course.units.map((unit) => {
          const unitDone = unit.items.filter((item) => isDone(progress, item)).length;
          return (
            <section key={unit.id} class="overview-unit">
              <h3>
                {unit.title}{" "}
                <span class="muted">
                  {unitDone}/{unit.items.length}
                </span>
              </h3>
              <ol>
                {unit.items.map((item) => (
                  <li key={`${item.kind}:${item.id}`}>
                    <button type="button" class="link" onClick={() => onOpen(item)}>
                      {isDone(progress, item) ? "✓ " : ""}
                      {item.title}
                    </button>
                    <span class="muted"> {item.kind}</span>
                  </li>
                ))}
              </ol>
            </section>
          );
        })}
      </div>
    </section>
  );
}
