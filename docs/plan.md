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
| First ~100 cards | Start with ~43 cards covering common beginner errors, then rank the rest by the Phase 1 error log | M4 |
| Licence and open source | None yet, so all rights are reserved until decided. Recommended: MIT for code, CC BY 4.0 for cards and curriculum. | Before the first public release |
| Training hardware | Laptop RTX 3050 (4 GB) for development and fine-tuning. A rented 24 GB GPU for a day of Track B pretraining. | M7 |
| Hosting | Cloudflare Pages: static, free, and allows the custom headers cross-origin isolation needs | M3 |

## M0: Repo foundation

- [x] `CLAUDE.md`, `README.md`, `docs/vision.md`, `docs/architecture.md`, `docs/plan.md`
- [x] `.gitignore`, `.editorconfig`, root `ruff.toml`
- [x] Engine package skeleton (src layout, `pyproject.toml`, pytest)
- [x] CI: lint, format check and tests on every push and PR

**Done when:** a fresh clone plus the commands in `CLAUDE.md` gives green lint
and tests, and CI is green.

## M1: Engine core

The shared library everything else builds on.

- [ ] `facts.py`: Diagnostic, Finding, Fix and RenderedCard, with JSON
      serialisation (`to_dict`) for the JavaScript side
- [ ] `syntax.py`: `compile()` to a Diagnostic for SyntaxError,
      IndentationError and TabError, with normalised positions
- [ ] `sandbox.py`: in-process execution with stdin fed from a list, captured
      stdout, a step budget for infinite loops, facts from the learner's
      deepest traceback frame, and collapsed recursion
- [ ] `isolated.py`: the sandbox in a subprocess with a hard timeout
- [ ] `style.py`: naming (variables, functions, classes), shadowed builtins,
      `== None` and `== True`/`False`
- [ ] `features.py`: extractors (similar names in learner code, misspelled
      builtins, missing imports, a name defined later, values that come from
      `input()`, in-place method results, keyword used as a name, and so on)
- [ ] `cards.py`: TOML schema, loader, validator and the most-specific-wins
      matcher
- [ ] Starter card library with examples:
  - syntax: `missing-colon`, `assign-in-condition`, `indent-expected`,
    `unexpected-indent`, `unindent-mismatch`, `tabs-and-spaces`,
    `unterminated-string`, `bracket-never-closed`, `bracket-unmatched`,
    `print-statement`, `missing-comma`, `keyword-as-name`
  - names: `name-typo`, `builtin-typo`, `missing-import`,
    `used-before-assignment`, `name-meant-string`, `name-undefined`,
    `unbound-local`
  - types: `str-plus-int`, `input-is-string`, `not-callable`,
    `not-subscriptable`, `int-not-iterable`, `str-immutable`,
    `missing-argument`
  - values and other: `index-out-of-range`, `key-missing`, `zero-division`,
    `int-conversion`, `none-attribute`, `attribute-typo`,
    `attribute-missing`, `recursion-limit`, `module-not-found`,
    `infinite-loop`, `input-exhausted`
  - style: `naming-variable`, `naming-function`, `naming-class`,
    `builtin-shadowed`, `compare-none`, `compare-bool`
- [ ] `fixes.py`: fix generators and the verification rule from
      `architecture.md`
- [ ] `engine.py`: `Engine.check(source)` for live static checks and
      `Engine.run(source, inputs)` for the full run
- [ ] CLI: `python -m pymentor check FILE [--run] [--input VALUE ...]`

**Done when:**

- Every card's examples trigger that exact card, and every card with a fix
  yields a verified fix on its examples.
- The design doc's mockup program gives a red `missing-colon` card on line 2
  and a blue `naming-variable` card on line 4.
- A test confirms the package imports only the standard library.
- The full test suite runs in under 10 seconds.

## M2: Exercises and logic errors

- [ ] Exercise format (TOML): id, title, prompt (Markdown), starter code,
      reference solution, tests (function calls, or stdin to expected stdout)
      and hints
- [ ] Test runner that turns failures into LOGIC diagnostics ("expected 15, got
      10"), with the test details in `data`
- [ ] Logic cards: `test-failed` (generic), `printed-not-returned`
      (the function returns `None` but printed the expected value),
      `wrong-output`
- [ ] 15–20 seed exercises for the first lessons. The validator checks that
      every reference solution passes and every starter fails or is
      incomplete.

**Done when:** the exercise validator runs in CI and `printed-not-returned`
triggers on its example.

## M3: Web app MVP (the Phase 1 core loop)

- [ ] `app/`: Vite, TypeScript, Preact and CodeMirror 6
- [ ] Pyodide in a dedicated Web Worker, with the engine wheel served as a
      static asset. Pin the Pyodide version and assert that its Python matches
      the engine target (D15).
- [ ] Live check on line leave or a ~600 ms pause, via `Engine.check`, shown as
      CodeMirror diagnostics coloured by severity
- [ ] Run with real `input()` through SharedArrayBuffer and Atomics (D9). Kill
      the worker after a wall-clock timeout, with the step budget giving the
      friendly card (D8).
- [ ] Correction card: badge, title, before/after, why, and the three actions:
      **Accept fix**, **Let me try first** (hint ladder from card hints) and
      **Why does Python work this way?** (the card's depth-3 text until the
      model arrives)
- [ ] Exercise view: prompt, editor, Run tests, purple findings
- [ ] PWA: works offline after the first load (service worker caches Pyodide
      and the engine)
- [ ] CI runs the engine test suite inside Pyodide (Node and the `pyodide` npm
      package)
- [ ] Performance budgets: first load ≤ ~15 MB transferred, live check < 50 ms,
      interactive in < 5 s from cache on a throttled low-end profile
- [ ] Accessibility: severity is never shown by colour alone (badge text and
      icon), keyboard-operable cards, screen-reader labels

**Done when:** the design doc's mockup is reproducible in the browser offline,
and the app installs as a PWA and works under CPU throttling.

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
