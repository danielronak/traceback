# Data card: seed corpus

The seed corpus is the correct beginner code that the bug mutators break to
make training and evaluation examples (M5). It's loaded by
`pymentor_pipeline.corpus.load_seeds`.

## Contents

| Source | Count | Where |
| --- | --- | --- |
| Standalone programs | 60 | `pipeline/corpus/programs/*.py` |
| Exercise reference solutions, with the exercises' tests | 18 | `curriculum/exercises/*.toml` |
| Runnable lesson snippets (deliberate mistakes excluded) | 28 | `curriculum/lessons/*.md` |
| **Total** | **106** | |

The programs cover the course's topics: printing, variables and `input()`,
numbers and text, functions, decisions, loops, strings, lists, dictionaries,
sets, tuples, small classes, and `try`/`except`. They are 4 to 15 lines long,
the size of a beginner's exercise.

## Provenance and licence

Every seed was **written for PyMentor** and is licensed with the repository.
No third-party code, scraped data or model output is included, so there are no
upstream licences or terms of use to track.

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

- 106 seeds written by one author: the style is consistent, but narrower than
  real learners' code. Phase 1's opt-in feedback (M4) should broaden the
  benchmark with real beginner mistakes (benchmark v1).
- No programs use files, networking or third-party libraries, matching what
  the browser app supports.
