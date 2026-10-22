# PyMentor

*Working title.* A free app that teaches Python the way a patient teacher would.
It underlines your mistakes as you code, explains why Python works that way, and
helps you fix them yourself. Think Grammarly for Python, built to teach rather
than just correct.

- **Free and local.** Everything runs on your own device: the Python runtime,
  the correction engine and, later, a small tutor language model. No accounts,
  no servers, no usage limits.
- **Grounded.** Python's own tooling decides what is wrong and whether a fix
  works. A library of hand-checked rule cards supplies the reasoning. The tutor
  model only puts those verified facts into words.

## Status

Early development. See [`docs/plan.md`](docs/plan.md) for the roadmap and
current milestone.

| Part | Directory | Status |
| --- | --- | --- |
| Correction engine and 51 rule cards | [`engine/`](engine/) | Working (M1 done) |
| Exercises and logic errors | `engine/` | Next (M2) |
| Web app | `app/` | Planned (M3) |
| Tutor model training | `training/` | Planned (M6, M7) |
| VS Code extension | `extension/` | Planned (M9) |

## Try the engine

Requires Python 3.13.

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e "engine[dev]"
python -m pymentor check my_program.py --run
```

## Documentation

- [Vision](docs/vision.md): what we're building and why
- [Architecture](docs/architecture.md): how it fits together, with the decision log
- [Plan](docs/plan.md): milestones and done-criteria
- [CLAUDE.md](CLAUDE.md): conventions for contributors, human or AI
