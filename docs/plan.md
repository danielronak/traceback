# Implementation plan

The order follows the design doc: **build the teacher first and treat the
model as an upgrade.** Each milestone ends with something that works on its
own. Tick boxes as work lands, and record decisions in the decision log in
`docs/architecture.md`.

```
M0 repo ─► M1 engine ─► M2 exercises ─► M3 web app ─► M4 content ═► Phase 1 ships
                │                                                        │ gate: real learners
                └──► M5 data + benchmark ─► M6 Track A ─┐                ▼
                                          └► M7 Track B ─┴─► M8 model in app ═► Phase 2
                                                                         │ gate: benchmark
                                                                         ▼
                                                              M9 VS Code ═► Phase 3
```

M5 depends only on M1, so the data pipeline can be built alongside the app.
Phase 1's opt-in error log then feeds the real-learner benchmark.

## Working assumptions

These are defaults until decided otherwise. They come from the design doc's
open questions.

| Question | Current default | Revisit |
| --- | --- | --- |
| Primary learner | Absolute beginners (school, college, career switchers all start here) | M4, from learner feedback |
| Languages at launch | English. Card text is kept in plain fields so it can be translated, with Hindi as the first candidate. | M8 |
| Base model for Track A | Shortlisted at build time: ≤500M parameters, permissive licence, code in its pretraining data | M6 |
| Final name | "PyMentor" is a working title. The package is `pymentor`, and renaming it is a find-and-replace. | Before the first public release |
| First ~100 cards | Start with 51 cards covering common beginner errors (done in M1), then rank the rest by the Phase 1 error log | M4 |
| Licence and open source | None yet, so all rights are reserved until decided. Recommended: MIT for code, CC BY 4.0 for cards and curriculum. | Before the first public release |
| Training hardware | Laptop RTX 3050 (4 GB) for development and fine-tuning. A rented 24 GB GPU for a day of Track B pretraining. | M7 |
| Hosting | Cloudflare Pages: static, free, and allows the custom headers cross-origin isolation needs | M3 |

## M0: Repo foundation ✅

- [x] `CLAUDE.md`, `README.md`, `docs/vision.md`, `docs/architecture.md`, `docs/plan.md`
- [x] `.gitignore`, `.editorconfig`, root `ruff.toml`
- [x] Engine package skeleton (src layout, `pyproject.toml`, pytest)
- [x] CI: lint, format check and tests on every push and PR

**Done when:** a fresh clone plus the commands in `CLAUDE.md` gives green lint
and tests, and CI is green.

## M1: Engine core ✅

The shared library everything else builds on.

- [x] `facts.py`: Diagnostic, Finding, Fix and RenderedCard, with JSON
      serialisation (`to_dict`) for the JavaScript side
- [x] `syntax.py`: `compile()` to a Diagnostic for SyntaxError,
      IndentationError and TabError, with normalised positions
- [x] `sandbox.py`: in-process execution with stdin fed from a list (or a
      callable, for the browser), captured stdout, a step budget for infinite
      loops, facts from the learner's deepest traceback frame, and collapsed
      recursion
- [x] `isolated.py`: the sandbox in a subprocess with a hard timeout
- [x] `style.py`: naming (variables, functions, classes), shadowed builtins,
      `== None` and `== True`/`False`
- [x] `features.py`: extractors (similar names in learner code, misspelled
      builtins, missing imports, a name defined later or only inside a
      function, values that come from `input()`, in-place method results, a
      keyword used as a name, loop conditions that never change, and so on)
- [x] `cards.py`: TOML schema, loader, validator and the most-specific-wins
      matcher
- [x] Starter card library: 51 cards, each with examples the tests check
  - syntax (13): `missing-colon`, `assign-in-condition`, `indent-expected`,
    `unexpected-indent`, `unindent-mismatch`, `tabs-and-spaces`,
    `unterminated-string`, `bracket-never-closed`, `bracket-unmatched`,
    `bracket-mismatch`, `print-statement`, `missing-comma`, `keyword-as-name`
  - names (10): `name-typo`, `builtin-typo`, `missing-import`,
    `used-before-assignment`, `name-in-function`, `name-meant-string`,
    `name-undefined`, `unbound-local`, `module-typo`, `module-not-found`
  - types (11): `input-is-string`, `str-plus-int`, `called-shadowed-builtin`,
    `not-callable`, `brackets-for-call`, `not-subscriptable`,
    `int-not-iterable`, `str-immutable`, `missing-argument`,
    `int-conversion-decimal`, `int-conversion`
  - lookups (6): `index-out-of-range`, `key-missing`,
    `none-from-inplace-method`, `none-attribute`, `attribute-typo`,
    `attribute-missing`
  - running (5): `zero-division`, `recursion-limit`,
    `loop-condition-unchanged`, `infinite-loop`, `input-exhausted`
  - style (6): `naming-variable`, `naming-function`, `naming-class`,
    `builtin-shadowed`, `compare-none`, `compare-bool`
- [x] `fixes.py`: 22 fix generators and the verification rule from
      `architecture.md`
- [x] `engine.py`: `Engine.check(source)` for live static checks and
      `Engine.run(source, inputs)` for the full run. Style findings also show
      behind a syntax error (D19).
- [x] CLI: `python -m pymentor check FILE [--run] [--input VALUE ...] [--json]`

**Done when:**

- Every card's examples trigger that exact card, and every card with a fix
  yields a verified fix on its examples.
- The design doc's mockup program gives a red `missing-colon` card on line 2
  and a blue `naming-variable` card on line 4.
- A test confirms the package imports only the standard library.
- The full test suite runs in under 10 seconds.

## M2: Exercises and logic errors ✅

- [x] Exercise format (TOML, one exercise per file in `curriculum/exercises/`):
      id, title, prompt (Markdown), starter code, reference solution, hints,
      and tests of two kinds: `call` (an expression and its expected value)
      and `output` (inputs and the expected printed output) (D21)
- [x] Test runner (`exercises.py`) that turns failures into LOGIC
      diagnostics at the tested function's `def` line, with the test details
      in `data`. Only the first failure becomes a finding; all results are
      reported (D22).
- [x] Fixes inside exercises are verified by re-running the exercise's tests
      (D23)
- [x] 12 new cards in `logic.toml` (63 in total): `printed-not-returned`
      (with a `print` → `return` fix), `missing-return`,
      `returned-text-not-number`, `off-by-one`, `test-failed`,
      `function-never-called`, `nothing-printed`, `input-joined-as-text`
      (with an `int(input())` fix), `wrong-output`, and, for crashes in the
      test call itself, `expected-function-misnamed`,
      `expected-function-missing` and `test-call-signature`
- [x] 18 seed exercises. Some starters are blank templates and some are
      "fix the bug" programs aimed at a specific card. The validator checks
      that every solution passes with no findings at all, and that every
      starter compiles, fails, and is taught by a card.
- [x] CLI: `python -m pymentor exercise EXERCISE.toml [FILE] [--json]`

**Done when:** the exercise validator runs in CI and `printed-not-returned`
triggers on its example. ✔

## M3: Web app MVP (the Phase 1 core loop) ✅

- [x] `app/`: Vite, TypeScript, Preact and CodeMirror 6
- [x] Pyodide 314 (Python 3.14) in a dedicated Web Worker, served from our own
      origin. The engine's source and the curriculum are bundled as text, so
      there's no wheel to build (D27). The worker refuses to start if its
      Python isn't the engine's target (D15, D25).
- [x] Live check on line leave or a 600 ms pause, shown as a wavy underline
      per kind of mistake, a gutter dot in the same colour, and a line tint for
      errors that stop the program
- [x] Run with streamed output and real `input()` through SharedArrayBuffer
      and Atomics (D9). Stop uses Pyodide's interrupt buffer; a watchdog
      restarts the worker if a program defeats the engine's own limits (D8).
- [x] Correction cards, try-first (D29): badge, title, rule, a hint ladder that
      ends at the fix, Show the fix with before/after, **Accept fix**, and
      **Why does Python work this way?** (the card's depth-3 text until the
      model arrives)
- [x] Exercise view: list, Markdown prompt, Run tests with a results list,
      purple findings, Start over, and drafts kept per exercise
- [x] PWA: a generated service worker precaches everything, so the app works
      offline after one visit, and adds the isolation headers for hosts that
      can't (D26). Chrome reports it installable.
- [x] CI: the engine on Python 3.13 and 3.14; the app's type-check, unit
      tests, the card and curriculum self-check inside Pyodide, and 9 Playwright
      end-to-end tests against the production build
- [x] Performance, measured at 4× CPU slowdown: 12.6 MB transferred on a cold
      load (uncompressed; about 5.5 MB compressed), Python ready in 3.1 s from
      cache, and a live-check card about 75 ms after typing
- [x] Accessibility: severity always has a text badge, cards and the console
      are keyboard-operable buttons and forms, and regions have labels

**Done when:** the design doc's mockup is reproducible in the browser offline,
and the app installs as a PWA and works under CPU throttling. ✔ (all three are
checked by tests or measured; see above)

**Follow-ups noted for M4:** keyboard users can leave the editor with Escape
then Tab (CodeMirror's convention) but nothing says so on screen; and the
budgets are measured on a desktop CPU slowed down, not on a real Chromebook.

## M4: Learning content and teaching behaviours (Phase 1 ships)

- [ ] Course structure: lessons (Markdown with runnable snippets) and
      exercises, ordered into a beginner course, plus a study-plan view
- [ ] Progress and mistake history in IndexedDB, local only
- [ ] Repetition becomes practice: after the same card N times, quiz the rule
      (quiz questions are stored on the card)
- [ ] "Try first" as the default, and hint-ladder state per finding
- [ ] Unknown-error log: errors with no card, stored locally. The learner can
      export it deliberately (opt-in).
- [ ] "Report this explanation" (local, exportable)
- [ ] Grow the card library towards ~100, ranked by the error log
- [ ] Deploy to Cloudflare Pages and get the first real learners

**Gate to Phase 2:** real learners are using it, and the error log shows which
cards matter.

## M5: Data pipeline and benchmark

Depends only on M1.

- [ ] `prompt.py`: task tokens and the code window (error line ±3 plus the
      enclosing function), shared by data generation and inference (D10)
- [ ] `grounding.py`: allowed line numbers, identifiers that must exist,
      code that must pass the engine, and lexical contradiction checks against
      the card (D11)
- [ ] Seed corpus of correct beginner programs, with sources and licences
      recorded
- [ ] Bug mutators: drop a colon, misspell a name, break indentation,
      `==` to `=`, off-by-one `range`, remove `str()`/`int()`, drop an import,
      unclose a bracket, a Python 2 `print`, `print` instead of `return`
- [ ] Generator CLI: mutate, run in `isolated.py`, keep examples with a matched
      card, dedupe, and split by seed program (D16). Output is JSONL.
- [ ] Teacher drafting script: a large model drafts outputs per task. Confirm
      and document that its terms of use allow training on its outputs. Add a
      small review tool for spot checks.
- [ ] Benchmark v0: ~300 held-out cases (hand-written plus mutations of
      held-out programs), frozen in `benchmark/v0/`
- [ ] Evaluation harness: scores any model callable on fix correctness,
      grounding rate, length and latency, and exports a hand-scoring sheet for
      clarity and hint quality
- [ ] Template baseline scored (D12)

**Done when:** the generator produces ≥20k verified examples and the harness
reports the template baseline.

## M6: Track A, fine-tuning an existing model (fallback and comparison)

- [ ] `training/` package, with its own dependencies (PyTorch, transformers)
- [ ] Shortlist and pick a base model, and record why
- [ ] SFT script (full fine-tune), with task tokens added as special tokens
- [ ] Evaluate, quantise to int4 ONNX, then re-evaluate, since tiny models are
      sensitive to quantisation
- [ ] Measure latency on CPU/WASM and WebGPU (D13)
- [ ] Optional: DPO with the automatic judge (the fix passes and grounding is
      clean)
- [ ] Model card with scores before and after quantisation

**Done when:** we know whether Track A clears the go/no-go criteria, with
numbers.

## M7: Track B, pretraining from scratch (the main experiment)

- [ ] Tokenizer: byte-level BPE with 16k entries on Python and programming
      English, with whitespace-run tokens. Compare tokens per character
      against base tokenizers.
- [ ] Pretraining data: download, filter, dedupe and write one `uint16`
      token file, plus a data card listing sources and licences
- [ ] Llama-style model via `LlamaConfig` (D14), with our own loop: bf16,
      `torch.compile`, fused AdamW, packing, cosine schedule, training at 512
      tokens then extending to 2,048, a checkpoint every 30–60 minutes,
      resumable runs, and sample generations logged at each checkpoint
- [ ] 10M smoke run on the laptop. Measure tokens per second and redo the
      sizing maths.
- [ ] ~50M main run (1–3 days on the laptop, or one day on a rented GPU)
- [ ] Fine-tune with the M6 script and evaluate with the same harness
- [ ] Write-up: size-versus-quality curves across both tracks, the key
      portfolio artefact

**Done when:** the comparison table and write-up are published.

## M8: The tutor model in the app (Phase 2)

- [ ] ONNX int4 model running in a worker with transformers.js (WebGPU, with a
      WASM fallback), with streaming output
- [ ] An optional download, cached, with its size shown. The app works fully
      without it.
- [ ] Jobs enabled per the quality gate: explain, hint ladder and why
      follow-ups. Logic errors and open-ended chat stay off unless proven.
- [ ] Every output passes grounding and code re-verification, or the card text
      is shown instead
- [ ] Go/no-go: faithfulness ≥95%, fix correctness, clarity, and the real
      learner test with 10–20 beginners

**Gate to Phase 3:** the model clears the benchmark bar.

## M9: The VS Code extension (Phase 3)

- [ ] Reuse the engine (the learner's local Python, or bundled Pyodide) and
      the ONNX model via onnxruntime-node
- [ ] Quiet when unsure: only findings with cards, and only frames in the
      learner's own code
- [ ] Diagnostics, code actions (fixes) and hover cards

## Cross-cutting rules

- **Privacy:** no network calls except fetching the app's own static assets.
  Exports are opt-in only.
- **Performance:** budgets are measured on a throttled low-end profile, not on
  a dev machine.
- **Internationalisation:** card text and UI strings live in data, never in
  code.
