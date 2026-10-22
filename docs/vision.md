# Vision

PyMentor (working title) is a free app that teaches Python the way a patient
teacher would. It underlines your mistakes as you code, explains why Python
works that way, and helps you fix them yourself. Think Grammarly for Python,
but built to teach rather than just correct.

This file condenses the original design doc ("PyMentor: A Local SLM That
Teaches Python", Oct 2026). `docs/architecture.md` describes how it is built
and `docs/plan.md` describes the order it is built in.

## Two equal purposes

1. **A genuinely shippable, free product.** Anyone can download it and learn
   Python. It starts as a full learning app and later adds a VS Code extension
   that acts as "training wheels" on learners' own projects.
2. **A portfolio project in task-specific SLMs.** It shows how small a model can
   be while still teaching well, how to ground it in verified facts so it
   doesn't hallucinate, and how to pretrain or fine-tune it, quantise it,
   evaluate it and ship it on-device.

## Principles

Every design decision traces back to these.

1. **Free forever, for everyone.** No subscriptions, usage caps or paywalls.
   Running costs stay near zero.
2. **Local and offline.** Code, model and Python runtime all run on the
   learner's device.
3. **Teach, don't just fix.** Hints come before answers, and the learner is
   invited to try first.
4. **Truth comes from tools, language comes from the model.** Python's own
   tooling decides whether there is an error, where it is, and whether a fix
   works. The model never invents errors, line numbers or rules.
5. **Data, not hardcoded logic.** Teaching knowledge lives in rule cards stored
   as data. Adding a lesson about an error means adding an entry.
6. **Lightweight enough for cheap hardware.** The full experience runs on
   budget laptops and school Chromebooks, and the smallest tutor model should
   run on a mid-range phone too (D45).

## The core experience

| Severity | Python equivalent | Caught by | Colour |
| --- | --- | --- | --- |
| Won't run | Syntax error | Compiler | Red |
| Crashes | Runtime error | Sandbox run | Orange |
| Style | PEP 8 / idiomatic Python | Style checks | Blue |
| Wrong answer | Logic error | Exercise tests | Purple |

Every correction can be explained at three depths:

1. **What to fix:** add a colon at the end of line 2.
2. **The rule:** every block header (`if`, `for`, `while`, `def`, `class`) ends
   with a colon.
3. **Why Python works this way:** Python groups code by indentation, and the
   colon signals that a new indented group starts.

A correction card shows a severity badge, a title, the line before and after
the fix, a short "why", and three actions: **Accept fix**, **Let me try
first** (hint ladder) and **Why does Python work this way?** (a conversation
with the local model).

Teaching behaviours:

- **Try first.** Hints come by default. The fix appears when asked for.
- **Hint ladder.** A nudge, then a clearer hint, then the fix.
- **Repetition becomes practice.** Repeating a mistake turns the fix into a
  quiz on the rule.
- **Gentle live checking.** A line is only checked once the cursor leaves it or
  typing pauses.

## The model's job

The tutor model reads Python and writes English. It turns a verified error,
its rule card and the learner's code into a short, personal explanation, hint
or answer. From easiest to hardest:

1. "But why?" follow-ups, grounded in the card
2. Personalised explanations around the learner's own names and code
3. The hint ladder
4. The long tail: errors with no card, tangled errors, long tracebacks
5. Logic errors (code runs but fails a test)
6. "What does this line do?"
7. Gentle code review
8. Targeted practice exercises

The model never detects errors, gives line numbers, states the official rule
or decides whether code is correct.

There are two training tracks, scored on the same benchmark:

- **Track B, from scratch (the main experiment):** pretrain a ~50–100M Python
  model on a laptop RTX 3050 (or a rented GPU for a day), then fine-tune it.
- **Track A, off the shelf (fallback and comparison):** fine-tune an existing
  ~135–500M permissively licensed model.

The app ships whichever passes the quality gate. Either outcome is a portfolio
result.

## Products and roadmap

1. **Phase 1, the app:** lessons, exercises and the correction engine with
   ~100 hand-reviewed rule cards. No model needed. *Gate: real learners are
   using it.*
2. **Phase 2, the tutor model:** an optional download that adds follow-ups,
   personalised explanations and the hint ladder. *Gate: the model passes the
   benchmark.*
3. **Phase 3, the VS Code extension:** the same engine and model on learners'
   own projects, and it stays quiet when unsure.

All three share one core library: the engine, the rule cards and the model
runtime.

## Go/no-go criteria for the model

- **Faithfulness:** at least 95% of explanations agree with the card and
  mention only real line numbers and names.
- **Fix correctness:** checked automatically. Broken fixes never reach
  learners.
- **Clarity:** a hand-scored sample is rated clear and pitched at beginner
  level.
- **Real learner test:** 10–20 beginners work through buggy exercises with and
  without the model.
