# pymentor-pipeline

PyMentor's training-data pipeline (M5). It is kept out of the engine package so
the browser never downloads it (D37). Standard library plus the engine.

```bash
uv pip install -e "pipeline[dev]"          # once, after the engine
python -m pymentor_pipeline generate        # writes data/generated/v1/
pytest pipeline
```

| Module | What it does |
| --- | --- |
| `corpus.py` | Loads the seed programs: `corpus/programs/`, exercise solutions, lesson snippets |
| `augment.py` | Renamed variants of each seed, kept only if they still pass cleanly |
| `mutate.py` | Bug mutators: one realistic beginner mistake per mutation |
| `generate.py` | Runs every mutation through the engine in killable workers, keeps carded findings, dedupes, splits by seed group (D16) and writes JSONL |
| `records.py` | Findings as JSON (with the features grounding needs) and back |

The output, in `data/generated/v1/` (not committed):

- `cases-{train,val,test}.jsonl`: one broken program per line, with its tests
  and the engine's finding.
- `examples-{train,val,test}.jsonl`: one model input per case and task, built by
  `pymentor.prompt` (D10). Targets are added later.
- `manifest.json`: counts per split, card and mutator, and a checksum per file.
