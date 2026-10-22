# CLAUDE.md

PyMentor (working title; the repo is named `traceback`) is a free, local,
offline app that teaches Python like a patient teacher. It is "Grammarly for
Python", built to teach rather than just correct. It has two equal goals: a
genuinely shippable free product, and a portfolio project showing that the
author can train, ground, quantise, evaluate and ship a task-specific small
language model (SLM).

Read these before making significant changes:

- `docs/vision.md`: what we're building and why (condensed design doc)
- `docs/architecture.md`: how it fits together, key contracts, decision log
- `docs/plan.md`: milestones, tasks and done-criteria. **Check what milestone
  we're on before starting work.**

## Non-negotiables

1. **Truth comes from tools, language comes from the model.** The model never
   detects errors, chooses line numbers, states rules or decides whether code
   is correct. Every fact comes from the engine. Any code the model writes is
   re-checked by the engine before it is shown, and on failure we fall back to
   the card text.
2. **Teaching knowledge is data.** Rule cards (TOML) hold the rules, reasons,
   hints and match conditions. Python code only extracts *features*. Don't add
   error-specific `if` branches in code when a card condition would do.
3. **Local and private.** At runtime, no network calls except fetching the
   app's own static assets. No telemetry. Any export is explicit and opt-in.
4. **Lightweight.** Target budget laptops and school Chromebooks. The engine
   has **zero runtime dependencies**, because it runs inside Pyodide.
5. **Free forever.** Nothing may cost money per user, so no servers.
6. **Teach, don't just fix.** Hints before answers. A fix is always offered,
   never forced.

## Repository layout

```
engine/      Python package `pymentor`: the shared core. Standard library only.
  src/pymentor/        engine modules (see docs/architecture.md for each)
  src/pymentor/cards/  the rule-card library (TOML), one file per topic
  tests/               test_cards.py self-tests every card from its examples
curriculum/  course content: course.toml, lessons/NN-id.md, exercises/NN-id.toml
app/         web app: Vite + TS + Preact + CodeMirror, Pyodide in a worker
pipeline/    training data, benchmark builder and evaluation harness (M5)
  corpus/              seed programs and their data card
training/    model training (M6/M7, not started)
benchmark/   frozen evaluation sets and results (v0)
docs/        vision, architecture, plan
```

## Commands

Run from the repo root.

```bash
uv venv .venv && source .venv/bin/activate   # once
uv pip install -e "engine[dev]"              # once
pytest engine                                # tests
ruff check . && ruff format --check .        # lint and format check
ruff format .                                # auto-format
python -m pymentor check path/to/file.py --run --input 5   # try the engine
python -m pymentor exercise curriculum/exercises/04-double.toml answer.py
```

The data pipeline (M5), also from the repo root. Generate data and build
benchmarks on Python 3.14, the version the app ships (D15):

```bash
uv pip install -e "pipeline[dev]"                    # once, after the engine
pytest pipeline                                      # tests
python -m pymentor_pipeline generate                 # data/generated/v1/ (not committed)
python -m pymentor_pipeline evaluate --model template   # score a model on benchmark v0
```

The web app, from `app/` (Node 22):

```bash
npm ci                         # once
npm run dev                    # dev server with the isolation headers input() needs
npm run typecheck && npm test  # TypeScript and unit tests (Vitest)
npm run test:engine            # card and curriculum self-check inside Pyodide
npx playwright test            # end-to-end, builds first; set PLAYWRIGHT_CHROMIUM
                               # to a Chromium binary if Playwright's isn't installed
```

CI (`.github/workflows/ci.yml`) runs all of the above, with the engine and the
pipeline on Python 3.13 and 3.14. Run the relevant ones locally before every commit.

## App conventions

- The engine's output shapes are mirrored in `app/src/engine/types.ts`. Change
  both together.
- Learner code only ever runs in the worker. The page never calls Python
  directly; it goes through `EngineClient`.
- No third-party requests at runtime: Pyodide is served from our own origin and
  cached by the service worker. Don't add CDN links.
- Severity is never shown by colour alone: keep the text badge on every card.
- Test UI changes in a real browser (`npx playwright test`). Several M3 bugs
  only showed up there.

## Engine conventions

- **Standard library only** in `engine/src/pymentor`. A test enforces this.
  Dev-only tools such as pytest are fine in `tests/`.
- **Python 3.14** is the target, matching Pyodide 314 (D15, D25), and 3.13 must
  keep working for learners' own Python. Python's error messages change between
  versions, and card `message` patterns depend on them.
- **Positions:** lines are 1-based, columns 0-based, ends exclusive, the same
  as `ast` and `traceback`. Convert `SyntaxError.offset` (1-based) at the
  boundary.
- **Never edit Python's message.** `Diagnostic.message` is Python's own text.
  Teaching wording belongs on cards.
- The public API is whatever `pymentor/__init__.py` exports. The JavaScript
  side consumes `to_dict()` output, so treat those shapes as a contract.
- Fix verification means "removes this error without a new one at or before
  its line", never "the program is correct". Keep the UI wording consistent
  with that.

## Rule cards

Cards live in `engine/src/pymentor/cards/*.toml`, grouped by topic. To add one:

1. Write the `[[card]]` entry with `id`, `title`, `match`, `rule`, `why`,
   `hints` (nudge, clearer hint, near-answer), and optionally `fix`,
   `exceptions` and `related`.
2. Add at least one entry to `examples`: a minimal program that triggers it.
   Add `inputs` if the program reads `input()`.
3. If no feature tells this cause apart from a sibling card, add an extractor
   to `features.py`, which is the only place cause-detection code lives.
4. Run `pytest engine`. The card tests check that each example triggers
   exactly this card, that every template renders, and that any fix verifies.

Card text rules:

- Cards are the **source of truth**. Every claim must be correct for Python
  3.13. Prefer fewer, accurate cards over many vague ones.
- Write for absolute beginners: plain words, short sentences, and explain any
  jargon on first use.
  - `rule` is the rule (depth 2).
  - `why` is the real reason Python works that way (depth 3).
- Use UK English (colour, recognise), matching the design doc.
- Placeholders such as `{name}` and `{line}` are filled from diagnostic facts
  and features. Never put facts in card text that the engine didn't produce.

## Exercises

Exercises live in `curriculum/exercises/NN-id.toml`, one per file. The number
sets the order and the rest must match `id`. Each has `id`, `title`, `prompt`
(Markdown), `starter`, `solution`, up to 3 `hints`, and `tests`:

```toml
tests = [
  { call = "double(4)", expect = "8" },          # expect is a Python literal
  { inputs = ["3", "4"], output = "7" },         # printed output; prompts don't count
]
```

`engine/tests/test_curriculum.py` checks every exercise: the solution must
pass with **no findings at all** (it's the model answer), and the starter must
compile, fail, and get a rule card as its first finding. A "fix the bug"
starter should aim at a specific card.

## Lessons

Lessons live in `curriculum/lessons/NN-id.md` and must be listed in
`curriculum/course.toml`, where every lesson and exercise appears exactly once.
A lesson starts with front matter:

```markdown
+++
id = "decisions"
title = "Making decisions with if"
teaches = ["missing-colon", "assign-in-condition"]   # rule-card ids
+++
```

Fenced `python` blocks are runnable snippets. Write ```` ```python broken=missing-colon ````
for a deliberate mistake, and `inputs=Ada|14` for answers to `input()`. CI
checks that ordinary snippets run with no findings, and that each broken one
is taught first by exactly the card it names, which must be in `teaches`.
Use `##` for sections (the lesson title is the heading above them).

## Testing

- Every behaviour change comes with tests. Engine tests must stay fast, with
  the whole suite under 10 seconds.
- Prefer real Python behaviour in tests (compile and run snippets) over mocks.
- When a Python upgrade changes a message, update the card pattern and note it
  in the decision log.

## Workflow

- Work milestone by milestone, following `docs/plan.md`. Tick boxes as tasks
  land.
- Record any significant technical decision, or any departure from the design
  doc, as a new entry in the decision log in `docs/architecture.md`.
- Keep commits small and focused, with messages scoped by area, such as
  `engine: add name-typo card` or `docs: update plan`.
- Don't add runtime dependencies to the engine. Ask before adding heavy
  dependencies elsewhere.

## Model and training (M5 onwards)

- The prompt format is defined once, in `pymentor.prompt`. Data generation,
  evaluation and inference all call it. Never duplicate it.
- Use only permissively licensed models and data. Record every source and its
  licence in a data or model card.
- Everything runs locally and free, including making training data: teachers
  are open-weight models on this machine, never a hosted or paid API (D40).
- Split train and evaluation data by seed program (D16). Never modify a frozen
  benchmark version; create a new version instead.
