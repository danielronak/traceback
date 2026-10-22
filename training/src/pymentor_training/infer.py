"""The tutor model as a callable, for the evaluation harness and for testing.

``Tutor(path)(item)`` returns the model's answer to a benchmark item, reading
only ``item.prompt``, exactly what it would see in the app. Decoding is greedy
and stops at ``<|end|>``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .data import END, prompt_ids

MAX_NEW_TOKENS = 256  # the longest task allows 150 words


class Tutor:
    def __init__(
        self,
        path: Path | str,
        *,
        device: str = "auto",
        max_new_tokens: int = MAX_NEW_TOKENS,
        onnx_file: str | None = None,
    ):
        """A trained model folder, or an exported one with ``onnx_file`` (for
        example ``model_q4.onnx``), run with onnxruntime on the CPU."""
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        if onnx_file is None:
            self.device = pick_device(device)
            self.model = AutoModelForCausalLM.from_pretrained(path).to(self.device).eval()
        else:
            from optimum.onnxruntime import ORTModelForCausalLM

            self.device = torch.device("cpu")
            self.model = ORTModelForCausalLM.from_pretrained(
                path, subfolder="onnx", file_name=onnx_file
            )
        self.end_id = self.tokenizer.convert_tokens_to_ids(END)
        self.max_new_tokens = max_new_tokens
        self.onnx_file = onnx_file

    def __call__(self, item: Any) -> str:
        return self.generate(item.prompt)

    @torch.inference_mode()
    def generate(self, prompt: str) -> str:
        ids = torch.tensor([prompt_ids(self.tokenizer, prompt)], device=self.device)
        out = self.model.generate(
            ids,
            attention_mask=torch.ones_like(ids),
            max_new_tokens=self.max_new_tokens,
            do_sample=False,
            eos_token_id=self.end_id,
            pad_token_id=self.tokenizer.pad_token_id,
        )
        text = self.tokenizer.decode(out[0, ids.shape[1] :], skip_special_tokens=False)
        return text.split(END, 1)[0].strip()

    @property
    def parameters(self) -> int | None:
        if self.onnx_file is not None:
            return None  # an exported graph; see export.json for its size
        return sum(p.numel() for p in self.model.parameters())


def pick_device(device: str = "auto") -> torch.device:
    if device != "auto":
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
