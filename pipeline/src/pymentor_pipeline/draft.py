"""Teacher drafting: a local open-weight model writes the training targets.

For each generated example, a *teacher* (any callable ``(system, prompt) ->
text``) writes the answer the tutor model should learn to give. Every draft is
then held to the same bar as the tutor itself:

- ``pymentor.grounding`` must accept it (line numbers, names, error types,
  leaks, length), and
- any code it contains must verify as a fix with the engine (``evaluate``).

Drafts that pass go to ``drafts-<split>.jsonl`` as training targets; the rest
go to ``rejected-<split>.jsonl`` with the reasons, for inspection. Runs are
resumable: examples already drafted or rejected are skipped.

Teachers run locally and are free: open-weight models with permissive
licences, never a hosted or paid API (D40). Record each teacher and its licence
in the data card before training on its drafts. ``teachers.py`` talks to a
model server on this machine.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from pymentor import grounding, prompt

from .evaluate import FENCE, Item, fix_verifies
from .generate import read_jsonl
from .records import finding_from_record

Teacher = Callable[[str, str], str | None]  # (system, prompt) -> text, or None if declined

TASK_GUIDE = {
    "explain": "Explain the error to the learner, using their own code and names. You may end "
    "with the fix from <|fix|> in a ```python block.",
    "hint_level_1": "A gentle nudge towards where to look. Don't say what to change.",
    "hint_level_2": "A clearer hint about what is wrong. Still don't show the fixed code.",
    "hint_level_3": "A near-answer: say what to change. You may show the fixed line(s) from "
    "<|fix|> in a ```python block.",
    "why_followup": "Answer the learner's <|question|> using the card's reason, about their code.",
    "review": "Gently review working code.",
    "logic_error": "Explain why the code gives the wrong answer for the failing test.",
}

SYSTEM = """You write the replies of a patient Python tutor for absolute beginners.

Each request gives the facts as tagged sections: <|task|>, <|level|>, <|error|> (the error \
Python reported and its line), <|card|> (the rule card: title, rule and reason), sometimes \
<|hint|>, <|fix|> (a fix the engine has already verified) or <|question|>, and <|code|> (the \
learner's code, each line starting with its real line number). Write only the reply for \
<|task|>: no preamble, no tags.

Truth comes from the facts, never from you:
- Mention only line numbers that appear in <|error|> or <|fix|>.
- In `backticks`, use only names that appear in the code, the card or the fix, or Python's \
own names.
- Name no error type except the one in <|error|>.
- Don't contradict the card or add rules it doesn't state.
- Any code you show must be the fixed line(s) from <|fix|>, in a ```python block, and only \
for the tasks that allow it.

Style: plain words, short sentences, UK English, speaking to the learner as "you". Use their \
names and code so it's about their program, not a generic one. Explain any jargon. Be warm \
but not gushing.

Tasks and their word limits:
{tasks}"""


def system_prompt() -> str:
    lines = [
        f"- {task} (at most {grounding.WORD_LIMITS[task]} words): {guide}"
        for task, guide in TASK_GUIDE.items()
    ]
    return SYSTEM.format(tasks="\n".join(lines))


def judge(text: str | None, item: Item) -> list[str]:
    """Why a draft can't be a training target; empty means it can."""
    if text is None:
        return ["declined"]
    reasons = [str(p) for p in grounding.check(text, item.finding, item.source, item.task)]
    block = FENCE.search(text)
    if block is not None and not fix_verifies(item, block[1]):
        reasons.append("fix: the code doesn't verify as a fix")
    return reasons


def draft(
    data: Path,
    split: str,
    teacher: Teacher,
    *,
    name: str,
    limit: int | None = None,
    log: Callable[[str], object] = print,
) -> Counter[str]:
    """Draft targets for one split of a generated dataset, resuming if interrupted."""
    cases = {c["id"]: c for c in read_jsonl(data / f"cases-{split}.jsonl")}
    accepted_path = data / f"drafts-{split}.jsonl"
    rejected_path = data / f"rejected-{split}.jsonl"
    done = {(r["case"], r["task"]) for r in _rows(accepted_path) + _rows(rejected_path)}
    system = system_prompt()
    tally: Counter[str] = Counter()
    started = time.monotonic()
    todo = [e for e in read_jsonl(data / f"examples-{split}.jsonl") if _key(e) not in done]
    # `limit` is the total wanted for this split, so re-running the same command
    # resumes rather than drafting another `limit` on top.
    budget = None if limit is None else max(0, limit - len(done))
    for example in balanced(todo)[:budget]:
        item = _item(cases[example["case"]], example)
        text = teacher(system, example["prompt"])
        reasons = judge(text, item)
        row = {"case": example["case"], "task": example["task"], "teacher": name}
        if reasons:
            tally["rejected"] += 1
            _append(rejected_path, row | {"output": text, "reasons": reasons})
        else:
            tally["accepted"] += 1
            _append(
                accepted_path, row | {"prompt": example["prompt"], "target": prompt.target(text)}
            )
        done_now = sum(tally.values())
        if done_now % 100 == 0:
            log(f"  {dict(tally)}, {_pace(started, done_now)}")
    done_now = sum(tally.values())
    left = len(todo) - done_now
    log(f"{split}: {dict(tally)}, {_pace(started, done_now)} ({left} left)")
    return tally


def _pace(started: float, count: int) -> str:
    seconds = time.monotonic() - started
    return f"{seconds / max(count, 1):.1f} s per answer" if count else "no answers yet"


def accept_outputs(
    data: Path, split: str, outputs: Iterable[tuple[str, str, str | None]], *, name: str
) -> Counter[str]:
    """Judge outputs a local teacher made offline, as ``(case, task, text)`` triples."""
    cases = {c["id"]: c for c in read_jsonl(data / f"cases-{split}.jsonl")}
    prompts = {_key(e): e["prompt"] for e in read_jsonl(data / f"examples-{split}.jsonl")}
    tally: Counter[str] = Counter()
    for case_id, task, text in outputs:
        example = {"case": case_id, "task": task, "prompt": prompts[(case_id, task)]}
        reasons = judge(text, _item(cases[case_id], example))
        row = {"case": case_id, "task": task, "teacher": name}
        if reasons:
            tally["rejected"] += 1
            _append(data / f"rejected-{split}.jsonl", row | {"output": text, "reasons": reasons})
        else:
            tally["accepted"] += 1
            _append(
                data / f"drafts-{split}.jsonl",
                row | {"prompt": example["prompt"], "target": prompt.target(text)},
            )
    return tally


def balanced(examples: list[dict[str, Any]], seed: int = 0) -> list[dict[str, Any]]:
    """Examples in an order where any prefix is a balanced sample: shuffled, then
    one per card in turn, so a 500-example trial run covers every card it can
    instead of the first few seed programs."""
    by_card: dict[str, list[dict[str, Any]]] = {}
    for example in examples:
        by_card.setdefault(example["card"], []).append(example)
    rng = random.Random(seed)
    queues = [by_card[card] for card in sorted(by_card)]
    for queue in queues:
        rng.shuffle(queue)
    ordered = []
    while any(queues):
        for queue in queues:
            if queue:
                ordered.append(queue.pop())
    return ordered


def _item(case: dict[str, Any], example: dict[str, Any]) -> Item:
    return Item(
        case["id"],
        example["task"],
        example["prompt"],
        finding_from_record(case["finding"]),
        case["source"],
        tuple(case.get("inputs", ())),
        tuple(case.get("tests", ())),
    )


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return row["case"], row["task"]


def _rows(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


def _append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
