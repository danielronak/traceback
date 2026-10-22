# Architecture

How PyMentor is built. `docs/vision.md` covers what it is and why, and
`docs/plan.md` covers the order it is built in. The decision log at the end
records every significant technical choice, including where we deliberately
depart from the original design doc.

## The one rule

**The engine owns the truth, the model owns the language.** Every fact a
learner sees comes from deterministic tooling: whether there is a mistake, its
line and column, its severity, the rule, and whether a fix works. The model
only rewords verified facts into teaching, and anything it writes passes back
through the engine before display.

## Repository layout

```
engine/        Python package `pymentor`, the shared core. Standard library only.
  src/pymentor/
    facts.py       Diagnostic, Finding, Fix, RenderedCard: the engine's output types
    syntax.py      compile() -> syntax diagnostics
    sandbox.py     executes learner code: stdin, stdout, step budget, traceback facts
    isolated.py    same, in a subprocess with a hard timeout (CLI, data pipeline)
    style.py       AST style checks (naming, builtin shadowing, comparisons)
    features.py    feature extractors: facts about *why* an error happened
    cards.py       rule-card schema, loader, validator and matcher
    cards/*.toml   the rule-card library (data)
    fixes.py       deterministic fix generators and fix verification
    engine.py      the public Engine API: check(), run()
    prompt.py      the model input format (M5), shared by training and inference
    grounding.py   the faithfulness checker for model output (M5)
    exercises.py   exercise format, loader and test runner
    course.py      the course: units, lessons (Markdown + snippets) and exercises
    selfcheck.py   card, exercise and course checks, run under pytest and inside Pyodide
  tests/
pipeline/      Python package `pymentor_pipeline` (M5): never shipped to the browser (D37)
  corpus/        seed programs and DATA_CARD.md
  src/pymentor_pipeline/
    corpus.py      loads seeds: corpus programs, exercise solutions, lesson snippets
    augment.py     renamed variants of seeds
    mutate.py      bug mutators, one realistic beginner mistake each
    generate.py    runs mutations through the engine in killable workers, writes JSONL
    benchmark.py   builds and freezes benchmark versions
    evaluate.py    scores any model: grounding, length, verified fixes, latency
    baseline.py    the template baseline (D12)
    draft.py       teacher drafting, judged by grounding and fix verification (D40)
    teachers.py    the local teacher adapter (a model server on this machine only)
    review.py      spot-check tool for drafted targets
curriculum/    Course content: course.toml, lessons/*.md, exercises/*.toml
app/           Web app: Vite + TypeScript + Preact, CodeMirror 6, Pyodide in a Web Worker
  src/engine/    worker (Pyodide + engine), client (input, Stop, watchdog), types
  src/editor/    CodeMirror setup and position mapping
  src/cards/     correction cards, the hint ladder, quizzes and reports
  src/course/    course navigation, overview (study plan) and lesson reader
  src/progress/  progress and feedback in IndexedDB, as pure update functions
  src/settings/  the settings dialog
  src/sw.template.js  the service worker, filled in at build time
training/      Python package `pymentor_training` (M6, M7). PyTorch; never shipped.
  src/pymentor_training/
    data.py        drafts to token ids, section markers as special tokens, answer-only loss
    sft.py         the fine-tuning loop (resumable, low-memory options)
    infer.py       a trained model (PyTorch or ONNX) as a callable for the harness
    export.py      ONNX export and int4 quantisation, in transformers.js's layout
benchmark/     Frozen, versioned evaluation sets and their results (M5)
extension/     VS Code extension (M9)
docs/          vision, architecture, plan
```

## Data flow

```
learner code
    │
    ▼
┌──────────────────────── engine (deterministic) ─────────────────────────┐
│ syntax.py ──┐                                                           │
│ style.py  ──┼──► Diagnostic ──► features.py ──► cards.py ──► fixes.py   │
│ sandbox.py ─┤      (fact)        (why facts)     (match)    (generate   │
│ exercises ──┘                                               + verify)   │
└──────────────────────────────────────────────┬──────────────────────────┘
                                               ▼
                                Finding (diagnostic + card + verified fix)
                                               │
                     ┌─────────────────────────┴───────────────┐
                     ▼                                         ▼
            correction card UI                       prompt.py ──► tutor SLM
            (Phase 1: no model)                                     │
                                                                    ▼
                                             grounding.py + fix re-run ──► UI
                                             (failed? fall back to the card)
```

## Key contracts

### Diagnostic (the fact)

`severity` (syntax, runtime, style, logic), `code` (exception type such as
`NameError`, or a rule code such as `naming-variable`), `message` (Python's own
message, never edited), and the position: `line` and `end_line` are 1-based,
`col` and `end_col` are 0-based, and ends are exclusive. Extra facts go in
`data`.

### Rule cards (the verified knowledge)

TOML files in `engine/src/pymentor/cards/`. One card per *cause*, not per
error type: a typo, a variable used before assignment and a missing import
are all `NameError`, but each is a different lesson.

```toml
[[card]]
id = "name-typo"
title = "`{name}` is not defined. Did you mean `{similar_name}`?"
match = { code = "NameError", when = { similar_name = true } }
priority = 50
rule = "Python only knows names you've created. A misspelling is a brand-new, unknown name."
why = "Python can't guess what you meant, since a typo could also be a real variable you forgot to create."
hints = ["Look closely at `{name}` on line {line}.", "Compare it with the names you created earlier."]
fix = "replace_name:similar_name"   # generator, and the feature holding the replacement
examples = [{ source = "total = 0\nprint(totl)\n", after = "print(total)" }]
```

Matching: a card applies when `code` matches, the optional `message` regex
matches Python's message, and every `when` condition holds against the
extracted features. **The most specific card wins**: the highest `priority`
first, then the most conditions (a `message` pattern counts as one), then file
order. A condition of `true` means the feature is truthy, `false` means falsy
or missing, and any other value must be equal. Every card has at least one
`examples` entry, and the test suite checks that each example triggers exactly
that card and that its fix verifies. The library tests itself, so adding a
card never needs new test code.

### Fix verification

A fix is shown as verified only if the engine re-checks the fixed program and
confirms that **this error is gone and no new error has appeared at or before
its line**:

- **Syntax fixes:** the program compiles, or its first syntax error is now on a
  later line.
- **Runtime fixes:** re-run with the same stdin. The same exception at the same
  line is gone, and no new error is raised on that line.
- **Style fixes:** the diagnostic is gone and the program still compiles.

We say "this fix removes the error". We never say "your program is now
correct": fixing one error often reveals the next, and that is fine.

### Model input (M5)

The prompt format from the design doc lives in `pymentor/prompt.py`, and both
the data generator and the app's inference call that one function:

```
<|task|>hint_level_1
<|level|>beginner
<|error|>SyntaxError line 2: expected ':'
<|card|>Every block header ... ends with a colon. The colon marks where an indented block begins.
<|code|>
1 scores = [72, 85, 90]
2 if len(scores) > 2
3     print("Enough scores")
<|response|>
```

The tasks are `explain`, `hint_level_1`, `hint_level_2`, `hint_level_3`,
`why_followup`, `review` and `logic_error`. The code window is the error line
±3 lines plus the enclosing function, with real line numbers.

## Runtime environments

| Where | Python | Learner code runs in | Model runtime |
| --- | --- | --- | --- |
| Web app | Pyodide (CPython 3.13 on WebAssembly) | Web Worker, `sandbox.py` | ONNX via transformers.js (WebGPU, WASM fallback) |
| VS Code extension | Learner's local Python, or bundled Pyodide | subprocess, `isolated.py` | ONNX via onnxruntime-node |
| Data pipeline and CLI | CPython 3.13 | subprocess, `isolated.py` | n/a |

## Decision log

Each entry gives the decision, the reason, and its status. **Changes from the
design doc** are marked with ⚑.

**D1. The engine is a standard-library-only Python package shared by
everything.** Pyodide runs it unchanged in the browser. The VS Code extension
and the training-data generator import the same code, so the facts the model is
trained on are produced exactly as the facts it sees in production, with no
training/serving skew. A test enforces that the package imports nothing outside
the standard library. *Accepted.*

**D2. ⚑ Card matching is feature extraction in code plus conditions in
data.** The design doc says cards are found by "a single lookup on the error
type", but "one card per cause" needs more. Telling a typo from a missing
import needs logic: is a similar name defined, is this a module name? Small
extractors in `features.py` compute named facts, and cards declare conditions
on them. Teaching knowledge stays in data (principle 5), and the code is a
small, reusable set of extractors rather than hundreds of if-else branches.
*Accepted.*

**D3. ⚑ Phase 1 fixes come from deterministic fix generators.** The design
doc's pipeline has the model propose fixes, but Phase 1 ships with no model and
still offers "Accept fix". Cards name a generator (`insert_colon`,
`replace_name`, `add_import`, and so on) that edits the source precisely using
the positions Python reports. Later, model-proposed fixes go through the same
verification. Some cards have no safe automatic fix (an ambiguous indentation
fix, anything needing intent), and those offer hints only. *Accepted.*

**D4. ⚑ Fix verification means "removes this error", not "guaranteed to
work".** See *Fix verification* above. The UI copy must match. *Accepted.*

**D5. ⚑ Style checks are our own small AST rules, not Ruff.** Ruff is a Rust
binary. Its Python wheel can't run inside Pyodide, and its WASM build lives on
the JavaScript side and adds megabytes. Beginners need only a handful of rules
(naming conventions, shadowing builtins, `== None`), and each needs a card
anyway. We can revisit Ruff's WASM build for the VS Code extension, where real
projects need more rules. *Accepted.*

**D6. One syntax error at a time.** `compile()` stops at the first syntax
error. Pedagogically that's right: fix the first error first, which is how
Python itself behaves. Recovering multiple syntax errors is a non-goal for v1.
*Accepted.*

**D7. ⚑ Live checking is static only. Runtime errors appear on Run.** Running
code on every pause would repeat side effects, block on `input()` and hang on
infinite loops. Syntax and style are checked live, runtime errors when the
learner presses Run, and logic errors when they run exercise tests. *Accepted.*

**D8. Infinite loops get a friendly card, with a hard kill as backstop.**
`sandbox.py` enforces a step budget through `sys.settrace` and reports the
looping line as a diagnostic, so even an infinite loop gets taught. The app
also terminates the worker after a wall-clock timeout, in case learner code
defeats the trace hook with a bare `except:`. *Accepted.*

**D9. `input()` in the browser uses SharedArrayBuffer and Atomics.**
Beginner programs use `input()` constantly, and Pyodide needs synchronous stdin
from the worker. That requires cross-origin isolation (COOP/COEP headers), so
we host on a static host that allows custom headers (Cloudflare Pages), and our
own service worker adds the headers on hosts that can't (D26). *Accepted.
Validated in M3, including Stop while a program waits for input.*

**D10. The prompt format is defined once, in the engine.** `pymentor.prompt`
builds model inputs for data generation, evaluation and inference alike. If it
were duplicated, a single drifted newline could silently degrade the model.
*Accepted.*

**D11. The grounding checker lives in the engine, and three things use it.**
`pymentor.grounding` rejects outputs that mention line numbers outside the
facts, name identifiers absent from the code or card, or contain code that fails
the engine. It is (a) an evaluation metric, (b) the automatic judge for
preference tuning, and (c) a runtime filter: a rejected output falls back to the
card text. *Accepted.*

**D12. The no-model card rendering is an explicit evaluation baseline.** Any
model must beat the filled-in card template on the benchmark to justify its
download size. This makes "is the model worth it?" measurable. *Accepted.*

**D13. ⚑ One model export format: ONNX int4.** The design doc mentions both
GGUF (llama.cpp) and ONNX. A single format serves both the browser
(transformers.js / onnxruntime-web, using WebGPU with a WASM fallback) and VS
Code (onnxruntime-node), so we quantise, evaluate and debug one artefact. At
50–135M parameters, CPU/WASM inference is likely fast enough for 50–200 output
tokens, so WebGPU is a speed-up, not a requirement. *Proposed. Validated in
M6.*

**D14. Track B uses the Llama architecture via Hugging Face `LlamaConfig`
with our own training loop.** The model definition matches what on-device
runtimes support and what Track A models use. That way both tracks share the
fine-tuning, export and evaluation code, while the pretraining loop (bf16,
`torch.compile`, packing, checkpointing) is written by hand as the portfolio
piece. *Proposed.*

**D15. Target the Python version Pyodide ships.** Error messages
change between Python versions, and card `message` patterns depend on them. The
engine targets the CPython that the app's Pyodide ships (3.14 since D25), CI
tests that version, and the card library is also self-checked inside Pyodide
itself. *Accepted. Re-check when upgrading Pyodide.*

**D16. Benchmark and training data are split by seed program.** Mutations of
one correct program never appear in both training and evaluation, which
prevents a leaky benchmark. Benchmark versions are frozen (`benchmark/v0/`, and
so on). *Accepted.*

**D17. ⚑ Some logic errors get deterministic cards too.** Common logic
mistakes have detectable signatures: a function that `print`s instead of
`return`ing (the test sees `None`), or an off-by-one count. Feature-based cards
cover these before any model exists. The model handles the rest. *Accepted.*

**D18. Monorepo, one directory per deliverable.** The engine, app, training
code and extension evolve together and share cards and fixtures. The engine is
the only package the others depend on. *Accepted.*

**D19. ⚑ Style findings still show while a syntax error blocks the file.**
The design doc's mockup shows a red syntax error and a blue style hint at the
same time, but style checks need code that compiles. When the syntax error has
a verified fix that keeps every line in place, the engine checks style on the
fixed version and reports findings on the other lines, without fixes of their
own until the file compiles. *Accepted.*

**D20. Fix candidates are verified in order, and only the first one that
verifies is shown.** A generator can propose several candidates (for example,
tabs expanded to 4 spaces, then to 8), so one generator handles the
common variants of a mistake without guessing. A fix that only moves the error
is rejected: in `"Next: " + age + 1`, wrapping `input()` in `int()` would fail
again on the same line, so no fix is offered and the card's hints do the
teaching. *Accepted.*

**D21. Exercises live in `curriculum/`, not in the engine package.** Rule
cards are the engine's knowledge, so they ship inside it. Exercises are course
content that will grow with lessons in M4 and be edited by teachers. The
engine provides the format, loader and runner; the app bundles the
curriculum. A test validates every exercise in CI. *Accepted.*

**D22. A failing test is a LOGIC diagnostic at the function's `def` line, and
only the first failure becomes a finding.** Several failing tests for one
function usually share one cause, and teaching one thing at a time is the
design doc's principle. All results are still reported for the test panel. A
crash *in the test call itself* (the function is missing, or takes different
arguments) also points at the `def` line, not at line 1 of the learner's file.
*Accepted.*

**D23. Inside an exercise, fixes are verified by re-running its tests.** A
typo inside a function only crashes when a test calls it, so a plain run of
the program would "verify" any fix. `fixes.verify` takes a `recheck` function
that re-derives the facts from the exercise's tests. A logic fix must make its
own failing test pass without causing a crash. Without a recheck, logic fixes
are never shown. *Accepted.*

**D24. Exercise tests run in-process, whatever runner the engine has.** The
browser has no subprocesses, so this is the path that ships. If the data
pipeline (M5) runs exercises in bulk, it will need a subprocess wrapper like
`isolated.py`. *Accepted. Revisited in M5: the pipeline runs each whole
analysis in a spawned worker process with a hard timeout and a memory limit,
so the engine itself stays unchanged (D38).*

**D25. ⚑ The browser ships Python 3.14 (Pyodide 314), not 3.13.** Pyodide
moved to Python-version numbering. The 314 line is current; 0.29 (Python 3.13)
is the older one. The whole engine suite passed on 3.14 unchanged. The engine
still supports 3.13 (`requires-python >= 3.13`), since the VS Code extension
will run on learners' own Python, so CI tests both. *Accepted.*

**D26. Our own service worker, generated at build time, instead of a PWA
plugin.** It precaches every built file plus Pyodide, adds the isolation
headers itself (so `input()` works on hosts that can't set them, after one
automatic reload), and activates on the next visit rather than mid-session. It
matches cached files ignoring `Vary`: module scripts carry an `Origin` header
the precache requests didn't, and without that, offline loads fail. About 60
lines that we fully understand, instead of a dependency. *Accepted.*

**D27. The engine's source is bundled into the worker as text, not built as
a wheel.** Vite imports `engine/src/pymentor/**` as raw strings and the worker
writes them into Pyodide's file system. There's no build step to forget, the
browser runs exactly the code the tests check, and edits reach the dev server
instantly. The curriculum is bundled the same way and parsed by the engine, so
TOML has one parser. *Accepted.*

**D28. One worker does both live checks and runs.** Two Pyodide instances
would double memory on low-end devices. While a program runs (or waits for
input) live checks pause, and the app re-checks as soon as the run ends.
*Accepted.*

**D29. ⚑ Cards are try-first: the fix is hidden until asked for.** The design
doc's mockup shows the fix straight away, but its own principle says hints come
before answers. A card opens with the problem and the rule. The hint ladder's
last rung is the fix, and "Show the fix" is always one click away. Teachers may
want a setting for this (M4). *Accepted.*

**D30. Output is batched twice.** A loop printing thousands of lines used to
send a message per write and re-render per message, freezing the page. The
worker flushes every 50 ms or 4 KB (and before `input()` waits, and at the
end), and the page renders at most once per frame, flushing when a run
finishes so the last output always precedes the closing note. *Accepted.*

**D31. Lessons are Markdown with checked snippets.** A lesson file starts
with TOML front matter (`id`, `title`, `teaches`). Its fenced `python` blocks
become runnable snippets, and a fence can say `inputs=a|b` or
`broken=card-id`. The engine splits a lesson into Markdown and snippet parts,
so the app never parses fences. CI runs every snippet: ordinary ones must run
with no findings at all, and each broken one must be taught first by exactly
the card it names, which the lesson must list in `teaches`. Lesson
explanations and the engine therefore can't drift apart. *Accepted.*

**D32. ⚑ One Course mode instead of separate Exercises.** The design doc lists
lessons, courses and study plans; M3 had a flat exercise list. Course mode is
now the landing page: a sidebar of units with ticks, lessons and exercises in
order, and an overview as the study plan. The overview has Continue, plus
"Practise your weak spots", which ranks lessons by how often the learner has
hit the cards they teach. The playground stays for free experimenting.
*Accepted.*

**D33. Mistakes are counted from deliberate runs, once while on screen.**
Live checks run while typing, and a half-typed `if x` isn't a mistake yet, so
only Run and Run tests count. A mistake that stays from one run to the next
(same card, line and message) counts once: re-running unchanged code isn't
repeating a mistake. Make it, fix it, make it again, and it counts twice.
*Accepted.*

**D34. Quizzes hide the rule until answered.** A quiz that shows the rule
alongside it tests reading, not memory. When practice is due, the card shows
only its title and the question; a wrong choice is greyed out with a nudge
rather than the answer, and the right one reveals the explanation, the rule,
hints and fix, and resets the count. Lesson snippets never quiz: their
mistakes are examples, not the learner's. Quiz text isn't templated, because
a quiz is about the rule, not this code. *Accepted.*

**D35. Feedback is local until the learner downloads it, without their code
by default.** Errors with no card and reported explanations are kept in
IndexedDB (de-duplicated, capped at 200 each). Settings shows the counts and
offers a JSON download. The line of code involved is left out unless the
learner ticks a box, because learner code can be personal. Nothing is ever
sent automatically; there is no telemetry. *Accepted.*

**D36. Some silent bugs are caught as style.** `print("Hello {name}")` runs
without error but prints the braces. When a plain string contains
`{variable}` for a variable the program defines (and isn't a docstring or
used with `.format`), the engine reports `fstring-missing-f` with a verified
fix that adds the `f`. *Accepted.*

**D37. The data pipeline is a separate package, `pymentor_pipeline`.** The
engine is bundled into the browser, so the mutators, generator, benchmark
builder and harness live in `pipeline/` and depend on the engine, never the
other way round. Only `prompt.py` and `grounding.py` sit in the engine, because
inference in the app needs them too (D10, D11). *Accepted.*

**D38. ⚑ Training data comes from mutations, renamed variants and the engine's
own verdict.** 37 mutators each inject one beginner mistake into 146 correct
seed programs and two renamed copies of each (`augment.py`, kept only if they
still pass cleanly). Every mutation is analysed exactly as the app would,
inside a spawned worker with a 20-second timeout, and kept only if its first
finding has a card. Duplicates are cases that give an identical prompt. Splits
are by seed group (D16): a program with its variants, an exercise, or a whole
lesson. The default run gives about 17,000 cases and 85,000 examples (five
tasks each), covering 46 cards. Writing the mutators exposed engine blind
spots (doubled-letter keyword typos, bare words used as values, `x = x.sort()`
then `len(x)`, `int["5"]`, locals used before their line), fixed in the
engine. *Accepted.*

**D39. Benchmark v0: 300 cases across all 81 cards, built on Python 3.14.**
180 mutations of test-split seeds sampled evenly by card, the 117 hand-written
card examples (never used as seeds), and 3 course mistakes from test-split
groups. Each case freezes the engine's finding, so later engine changes can't
move the goalposts. Model-written code counts as a fix only if, put in place
of the broken line(s), the engine verifies it the same way it verifies its own
fixes, using the case's tests. The template baseline scores 100% grounded at
18.7 words per output and never writes code: a model must match that
grounding while being more personal, measured by hand. v0 was first built on
the 3.13 dev environment and rebuilt on 3.14 before anything but the template
had been scored; 2 of 300 cases differed. The builder now refuses any Python
but the app's. *Accepted.*

**D40. ⚑ Teachers are local, open-weight and free; never a hosted or paid
API.** The whole project stays local and free, including how its training data
is made. A teacher is a permissively licensed open-weight model running on the
owner's machine behind a local chat-completions server (llama.cpp's
`llama-server` or Ollama); `teachers.py` refuses any address that isn't this
machine. Its drafts face the tutor's own bar: grounding must pass and any code
must verify as a fix, or the draft is rejected with reasons. A spot-check tool
(`review.py`) records human verdicts on a sample. The teacher can be larger
than the tutor, since it never ships, but it must fit the laptop (RTX 3050):
roughly 3–8B parameters at 4-bit. Candidates to check, confirming the licence on
each model card at download time: Qwen2.5-7B-Instruct (Apache-2.0),
Mistral-7B-Instruct-v0.3 (Apache-2.0), Phi-3.5-mini-instruct (MIT), or newer
equivalents. Record the chosen model, its licence and the run date in the data
card. An earlier draft of this decision included an adapter for a paid API;
it was removed because it broke the free, local principle. The seed programs
were drafted with an AI coding assistant during development; that is recorded
in the corpus data card. *Accepted. The teacher model is picked with M6's base
model shortlist.*

**D41. The "Done when" for M5 counts verified model inputs.** The plan asked
for 20,000 verified examples. The generator produces about 85,000 engine-
verified prompts. Their targets come from a local teacher (D40), so the
training set proper is "drafts that passed grounding and fix verification",
counted once a teacher has run. *Accepted.*

**D42. ⚑ Track A compares two tutors; the teacher is Qwen3-4B-Instruct-2507.**
The owner chose to fine-tune both `HuggingFaceTB/SmolLM2-360M-Instruct` (Llama
architecture like Track B, 49k vocabulary, roughly 250 MB at int4) and
`Qwen/Qwen2.5-Coder-0.5B-Instruct` (code-heavy pretraining, 32k context, 152k
vocabulary, roughly 400 MB or more at int4), so the comparison measures what
the extra download buys. The teacher is `Qwen/Qwen3-4B-Instruct-2507`: about
2.5 GB at Q4_K_M, so it fits a 4 GB GPU, and it has no thinking mode to strip.
All are Apache-2.0 according to their families' official repositories
(QwenLM/Qwen3, huggingface/smollm); Hugging Face itself couldn't be reached
from the build machine, so each licence is confirmed again on its model card
at download time and recorded in `training/MODEL_CARD.md`. Considered and
left for later: Granite-4.0-350M (Apache-2.0, code in its training data).
Excluded for their licences: Gemma 3, Llama 3.2, LFM2. *Accepted.*

**D43. The training toolchain is transformers 4.57 plus optimum for export.**
The ONNX exporter (`optimum-onnx` 0.1) requires transformers below 4.58, and
one environment should train, export and evaluate, so the training package
pins `transformers>=4.46,<4.58`; the code also runs on transformers 5 apart
from export. Export writes transformers.js's layout (`onnx/model.onnx` and
`onnx/model_q4.onnx`, 4-bit MatMulNBits weights in blocks of 32, the scheme
transformers.js calls `q4`), and the harness scores the ONNX files directly
with onnxruntime, so quantisation loss is measured, not assumed. Training is
a full fine-tune sized for a laptop GPU: fp32 weights with bf16 autocast (fp16
with loss scaling on pre-Ampere GPUs), Adafactor and gradient checkpointing
for 4 to 6 GB cards. Tests train, resume and export a tiny Llama built on the
spot, on the CPU, so CI needs no downloads. *Accepted. Re-check when
optimum-onnx supports transformers 5.*

**D44. Full fine-tuning on a 4 GB GPU: step in backward, score answers only.**
The owner's RTX 3050 has 4 GB. Fp32 weights, gradients and Adafactor state
alone would need about 3.0 GB for SmolLM2-360M and 4.2 GB for
Qwen2.5-Coder-0.5B. Two changes keep it a full fine-tune that fits. First,
`--step-in-backward` (PyTorch's "optimizer step in backward" pattern) gives
each weight tensor its own optimizer, stepped by a hook as soon as its
gradient is ready, which then frees it. Only the largest tensor's gradient is
ever held, but gradient accumulation is impossible and clipping is per tensor;
a test shows it otherwise matches the standard loop exactly. Second,
`answer_loss` scores the vocabulary only at answer positions for
architectures whose head is a plain projection (Llama, Qwen2, Qwen3), with a
test showing it equals the model's own loss. Estimates: about 2.5 GB and
3.4 GB. These are calculated, not measured; the first real run confirms them.
LoRA was the alternative, but it changes what is being compared and adds a
dependency. *Accepted.*

**D45. ⚑ SmolLM2-135M joins Track A, for phones.** The owner wants the tutor
to run on any basic laptop and even a mid-range phone. SmolLM2-135M-Instruct
(Apache-2.0, roughly 100 MB at int4) gives Track A a three-point size curve
(135M, 360M, 500M) for the comparison with Track B's from-scratch model
(50 to 100M), and a phone-sized fallback if Track B falls short. Qwen 0.5B
stays in the comparison but is unlikely to ship to phones. Shipped or not,
every tutor only explains the facts the engine supplies about the learner's
own code, and the app falls back to the card when there is no model or an
answer fails grounding. *Accepted.*

**D46. The training runbook targets the owner's Windows laptop.** The owner
trains on Windows 11 with a 4 GB RTX 3050, so the runbook in
`training/README.md` is written for PowerShell. It installs PyTorch's CUDA build
explicitly, since the default Windows build is CPU-only, and uses Ollama as
the local teacher server, the simplest on Windows; llama.cpp works too. CI
runs the engine, pipeline and training suites on `windows-latest` as well, so
Windows-only failures show up before the owner hits them. `draft --limit` is
the total for a split, so re-running an interrupted command resumes it.
*Accepted.*
