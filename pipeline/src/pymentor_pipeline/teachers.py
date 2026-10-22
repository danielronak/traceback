"""The local teacher adapter for ``draft``.

Teachers are open-weight models running on your own machine, never a hosted
or paid API (D40): the project stays free and local end to end. Any local
server with the common chat-completions endpoint works, for example
llama.cpp's ``llama-server`` or Ollama. Standard library only.

    llama-server -m teacher-model.gguf --port 8080
    python -m pymentor_pipeline draft --model teacher-model --limit 500
"""

from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlparse

DEFAULT_URL = "http://127.0.0.1:8080/v1/chat/completions"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def local_teacher(
    url: str = DEFAULT_URL,
    *,
    model: str = "local",
    max_tokens: int = 400,
    temperature: float = 0.3,
    timeout: float = 300,
):
    """A teacher that asks a model server on this machine. Refuses any other host."""
    host = urlparse(url).hostname
    if host not in LOCAL_HOSTS:
        raise ValueError(f"teachers must run locally (D40); {host!r} isn't this machine")

    def teach(system: str, prompt: str) -> str | None:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        request = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            choice = json.load(response)["choices"][0]
        if choice.get("finish_reason") == "length":
            return None  # cut off mid-answer
        return (choice.get("message") or {}).get("content") or None

    return teach
