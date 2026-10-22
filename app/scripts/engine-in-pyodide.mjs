// Runs the engine's self-checks inside Pyodide: every rule card's examples and
// every exercise, on the exact Python version the app ships (D15, D25).
// Error messages change between Python versions, so CPython passing isn't
// enough. Usage: npm run test:engine
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";

const EXPECTED_PYTHON = "3.14";
const repo = fileURLToPath(new URL("../..", import.meta.url));

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (/\.(py|toml)$/.test(name)) yield path;
  }
}

const pyodide = await loadPyodide();
const version = pyodide.runPython("import sys; '%d.%d' % sys.version_info[:2]");
if (version !== EXPECTED_PYTHON) {
  console.error(`Pyodide ships Python ${version}, but the engine targets ${EXPECTED_PYTHON}.`);
  process.exit(1);
}
for (const [source, target] of [
  [join(repo, "engine/src/pymentor"), "/engine/pymentor"],
  [join(repo, "curriculum/exercises"), "/curriculum/exercises"],
]) {
  for (const path of files(source)) {
    const destination = join(target, relative(source, path));
    pyodide.FS.mkdirTree(destination.slice(0, destination.lastIndexOf("/")));
    pyodide.FS.writeFile(destination, readFileSync(path, "utf8"));
  }
}

const result = JSON.parse(
  pyodide.runPython(`
import json, sys
sys.path.insert(0, "/engine")
from pymentor import Engine
from pymentor.exercises import load_exercises
from pymentor.selfcheck import check_exercise, check_library

engine = Engine(step_limit=20_000)
exercises = load_exercises("/curriculum/exercises")
problems = check_library(engine)
for exercise in exercises:
    problems += check_exercise(engine, exercise)
examples = sum(len(card.examples) for card in engine.cards)
json.dumps({"cards": len(engine.cards), "examples": examples,
            "exercises": len(exercises), "problems": problems})
`),
);

console.log(
  `Python ${version} (Pyodide ${pyodide.version}): ${result.cards} cards, ` +
    `${result.examples} examples, ${result.exercises} exercises checked.`,
);
for (const problem of result.problems) console.error(`  FAIL ${problem}`);
process.exit(result.problems.length ? 1 : 0);
