"""Export a trained tutor to ONNX and quantise it to int4, for the browser (D13).

    python -m pymentor_training export --model training/runs/smollm2-360m/best \\
        --out training/runs/smollm2-360m/web

The output folder has the layout transformers.js loads: ``config.json``,
``generation_config.json`` and the tokenizer files at the top, and
``onnx/model.onnx`` (full precision) plus ``onnx/model_q4.onnx`` (4-bit weights
in blocks of 32, the same scheme transformers.js uses for ``q4``). Tiny models
are sensitive to quantisation, so both are scored on the benchmark:

    python -m pymentor_training evaluate --model .../web --onnx model_q4.onnx --name ...
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

BLOCK_SIZE = 32


def export(model: Path, out: Path, *, block_size: int = BLOCK_SIZE) -> dict[str, int]:
    """Write the ONNX model and its int4 version; returns each file's size in bytes."""
    import onnx
    from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer
    from optimum.exporters.onnx import main_export

    out = Path(out)
    with tempfile.TemporaryDirectory() as tmp:
        main_export(
            str(model),
            output=tmp,
            task="text-generation-with-past",
            device="cpu",
            do_validation=False,
        )
        shutil.rmtree(out, ignore_errors=True)
        (out / "onnx").mkdir(parents=True)
        for file in Path(tmp).iterdir():
            target = out / "onnx" if file.name.startswith("model.onnx") else out
            shutil.move(file, target / file.name)

    full = out / "onnx" / "model.onnx"
    quantiser = MatMulNBitsQuantizer(onnx.load(str(full)), block_size=block_size, is_symmetric=True)
    quantiser.process()
    q4 = out / "onnx" / "model_q4.onnx"
    quantiser.model.save_model_to_file(str(q4), use_external_data_format=False)

    sizes = {
        f.relative_to(out).as_posix(): f.stat().st_size for f in sorted((out / "onnx").iterdir())
    }
    (out / "export.json").write_text(
        json.dumps({"source": str(model), "block_size": block_size, "bytes": sizes}, indent=2)
        + "\n"
    )
    return sizes
