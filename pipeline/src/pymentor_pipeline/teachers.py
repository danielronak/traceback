"""Optional teacher adapters for ``draft``. Each one is a few lines; add others
the same way (any ``(system, prompt) -> text`` callable works).

Requires the ``teacher`` extra (``uv pip install -e "pipeline[teacher]"``) and
credentials in the environment. Before using any provider for training
targets, confirm its terms of use allow it and record that decision (see
``draft``).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000  # room for thinking; the replies themselves are short
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def anthropic_teacher(model: str = DEFAULT_MODEL, effort: str = "medium"):
    """A teacher calling the Messages API, one request at a time.

    Server-side refusal fallbacks are on, so a request a safety classifier
    declines is retried on a suitable model in the same call; a reply that is
    still a refusal counts as declined.
    """
    import anthropic

    client = anthropic.Anthropic()

    def teach(system: str, prompt: str) -> str | None:
        response = client.beta.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        return _text(response)

    return teach


def submit_anthropic_batch(
    examples: Iterable[dict[str, Any]],
    system: str,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = "medium",
) -> str:
    """Send examples as one Message Batch (half price, results within 24 hours).
    Returns the batch id. Batches take up to 100,000 requests; fallbacks
    aren't available there, so declined requests come back as refusals."""
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()
    requests = [
        Request(
            custom_id=f"{e['case']}:{e['task']}",
            params=MessageCreateParamsNonStreaming(
                model=model,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": e["prompt"]}],
                output_config={"effort": effort},
            ),
        )
        for e in examples
    ]
    return client.messages.batches.create(requests=requests).id


def anthropic_batch_results(batch_id: str) -> Iterator[tuple[str, str, str | None]]:
    """``(case, task, text)`` for each finished request; ``None`` text when it
    errored, expired or was declined. Pass these to ``draft.accept_batch``."""
    import anthropic

    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(batch_id)
    if batch.processing_status != "ended":
        raise RuntimeError(f"batch {batch_id} is still {batch.processing_status}")
    for result in client.messages.batches.results(batch_id):
        case, _, task = result.custom_id.rpartition(":")
        text = _text(result.result.message) if result.result.type == "succeeded" else None
        yield case, task, text


def _text(message: Any) -> str | None:
    if message.stop_reason in ("refusal", "max_tokens"):
        return None
    return "".join(block.text for block in message.content if block.type == "text") or None
