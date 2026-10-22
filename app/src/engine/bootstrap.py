# Glue between the web worker and the engine. Runs inside Pyodide; every
# function returns JSON text, which the worker passes to the page unchanged.
import json
import sys

sys.path.insert(0, "/engine")

from pymentor import Engine, Report
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


def load_exercises(items_json):
    loaded = []
    for origin, text in json.loads(items_json):
        exercise = parse_exercise(text, origin)
        _exercises[exercise.id] = exercise
        loaded.append(exercise.to_dict())
    return json.dumps(loaded)


def run_exercise(exercise_id, source):
    return json.dumps(_engine.run_exercise(_exercises[exercise_id], source).to_dict())
