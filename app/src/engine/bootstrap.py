# Glue between the web worker and the engine. Runs inside Pyodide; every
# function returns JSON text, which the worker passes to the page unchanged.
import json
import sys

sys.path.insert(0, "/engine")

from pymentor import Engine, Report
from pymentor.course import parse_course, parse_lesson
from pymentor.exercises import parse_exercise

_engine = Engine()
_exercises = {}


def check(source):
    return json.dumps(_engine.check(source).to_dict())


def run(source, ask, emit):
    def provider(prompt):
        answer = ask(prompt)
        if answer is None:  # the learner pressed Stop while we waited
            raise KeyboardInterrupt
        return answer

    try:
        report = _engine.run(source, provider, on_output=emit)
    except KeyboardInterrupt:  # Stop arrived outside the learner's code
        report = Report(stopped=True)
    return json.dumps(report.to_dict())


def load_curriculum(files_json):
    files = json.loads(files_json)

    def under(folder):
        return [(path, text) for path, text in files if path.startswith(f"curriculum/{folder}/")]

    lessons = [parse_lesson(text, path) for path, text in under("lessons")]
    exercises = [parse_exercise(text, path) for path, text in under("exercises")]
    course_text = next(text for path, text in files if path == "curriculum/course.toml")
    course = parse_course(course_text, lessons, exercises)
    _exercises.update(course.exercises)
    return json.dumps(
        {"course": course.to_dict(), "exercises": [e.to_dict() for e in course.exercises.values()]}
    )


def run_exercise(exercise_id, source):
    return json.dumps(_engine.run_exercise(_exercises[exercise_id], source).to_dict())
