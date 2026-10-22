# pymentor (engine)

PyMentor's deterministic core. It finds mistakes in Python code using Python's
own compiler, a sandboxed run and a few style checks, matches each mistake to a
hand-written rule card, and produces fixes the engine has re-checked.

It uses only the standard library, so the same code runs in the browser (via
Pyodide), in the VS Code extension and in the training-data pipeline.

```python
from pymentor import Engine

engine = Engine()
report = engine.check("if x > 2\n    print(x)\n")  # live, static checks
report = engine.run(source, inputs=["5"])  # also runs the code
for finding in report.findings:
    print(finding.diagnostic.line, finding.card.title)
```

See `docs/architecture.md` at the repository root for the design.
