# Benchmarks

Frozen evaluation sets for the tutor model. A version is **never modified**
once built (CLAUDE.md); a better benchmark is a new version. A test checks each
version against its `SHA256SUMS`.

```bash
python -m pymentor_pipeline evaluate --model template     # score the baseline
python -m pymentor_pipeline evaluate --model my_pkg.infer:generate
python -m pymentor_pipeline evaluate --outputs runs/model-a.jsonl  # saved outputs
```

Each run writes `results/<version>/<name>.json` (automatic scores), the outputs
it scored, and `<name>-hand-scoring.csv`: 12 outputs per task with empty
columns for clarity, hint quality and accuracy, to be scored by people.

## v0

300 cases, every one with a rule card, covering all 81 cards. Built with
`python -m pymentor_pipeline benchmark` from the engine as of commit `26c2e8d`,
prompt format version 1.

| Origin | Cases | Where from |
| --- | --- | --- |
| `mutation` | 180 | Mutations of test-split seeds (D16), sampled evenly across cards |
| `card-example` | 117 | The hand-written example on every card; never used as seeds |
| `lesson-mistake` | 2 | Deliberately broken lesson snippets in test-split lessons |
| `exercise-starter` | 1 | "Fix the bug" starters of test-split exercises |

Each line of `cases.jsonl` holds the learner's program, its `inputs` and
`tests`, and the engine's finding at build time (diagnostic, rendered card,
verified fix and features). Prompts are rebuilt from those frozen facts with
`pymentor.prompt`, so every model sees exactly what it would see in the app.
Every case gives 5 items (explain, three hint rungs, and "why?"): 1,500 in all.

### Scores

| Model | Grounded | Mean words | Over limit | Writes a verified fix |
| --- | --- | --- | --- | --- |
| Template baseline (D12) | 100% | 18.7 | 0% | never writes code |

The template is grounded by construction: it *is* the card. What it can't do is
use the learner's own names and code, or answer a different "why?". That's the
gap a model must close, measured by the hand-scoring sheet, without giving up
grounding.

### Known limitations

- Only 3 cases come from the course, because just one exercise and one lesson
  group fall in the test split. Benchmark v1 should add real learners' mistakes
  from opt-in feedback (M4).
- Mutations are sampled evenly by card, so v0 over-represents rare cards
  relative to what learners hit. That's deliberate: it tests the long tail.
