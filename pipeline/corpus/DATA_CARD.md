# Data card: seed corpus

The seed corpus is the correct beginner code that the bug mutators break to
make training and evaluation examples (M5). It's loaded by
`pymentor_pipeline.corpus.load_seeds`.

## Contents

| Source | Count | Where |
| --- | --- | --- |
| Standalone programs | 100 | `pipeline/corpus/programs/*.py` |
| Exercise reference solutions, with the exercises' tests | 18 | `curriculum/exercises/*.toml` |
| Runnable lesson snippets (deliberate mistakes excluded) | 28 | `curriculum/lessons/*.md` |
| **Total** | **146** | |

The programs cover the course's topics: printing, variables and `input()`,
numbers and text, functions, decisions, loops, strings, lists, dictionaries,
sets, tuples, small classes, and `try`/`except`. They are 4 to 30 lines long,
the size of a beginner's exercise. Programs 061 to 100 deliberately use the
shapes the runtime mutators need: dictionary lookups with literal keys, `while`
loops with counters, functions with several parameters, in-place list methods
and string methods.

## Provenance and licence

Every seed was **written for PyMentor** and is licensed with the repository.
No third-party code or scraped data is included.

The standalone programs (001 to 100) were drafted with an AI coding assistant
(Claude, via Claude Code) while building the project, then checked by the
engine as described below. The exercise solutions and lesson snippets were
written the same way. So the seeds are model output, though only as *inputs*:
they are correct programs that the mutators break, never the explanations the
tutor model learns to write. Whether the assistant's terms of use allow this
use is the project owner's call, and is recorded with the teacher-drafting
decision (M5).

If outside code is ever added, record each source here, with its licence and
how it was filtered. Only permissively licensed code (MIT, Apache 2.0, BSD,
CC0, CC BY) may be used (CLAUDE.md, "Model and training").

## Guarantees (checked by `pipeline/tests/test_corpus.py`)

- Every seed runs with **no findings at all** from the engine: no errors and
  no style notes. Seeds are model answers.
- Every seed prints the same thing on every run. No randomness, clock or
  environment dependence, because a seed's output becomes its own test.
- Programs that read `input()` say what to answer in a first-line comment:
  `# inputs: Ada | 14`.

## Known limitations

- 146 seeds from one source: the style is consistent, but narrower than real
  learners' code. Renamed variants (`augment.py`) widen the names, not the
  shapes. Phase 1's opt-in feedback (M4) should broaden the
  benchmark with real beginner mistakes (benchmark v1).
- No programs use files, networking or third-party libraries, matching what
  the browser app supports.
