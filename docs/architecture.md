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
    exercises/     exercise format and test runner (M2)
    data/          bug injection and the training-data generator (M5)
  tests/
app/           Web app (M3): Vite + TypeScript, CodeMirror 6, Pyodide in a Web Worker
training/      Model training (M6, M7): tokenizer, pretraining, SFT, export. PyTorch.
benchmark/     Frozen, versioned evaluation sets (M5)
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
we host on a static host that allows custom headers (Cloudflare Pages), with
`coi-serviceworker` as a fallback. *Proposed. Validated in M3.*

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

**D15. Target Python 3.13, pinned to Pyodide's version.** Error messages
change between Python versions, and card `message` patterns depend on them. The
engine targets the CPython version that Pyodide ships, and CI tests that
version. *Accepted. Re-check when upgrading Pyodide.*

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
