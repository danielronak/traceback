"""Examples are tokenised with atomic section markers, and only targets count."""

from transformers import AutoModelForCausalLM, AutoTokenizer

from pymentor import prompt
from pymentor_training.data import IGNORE, Example, add_special_tokens, collate, encode


def test_section_markers_become_single_tokens_and_embeddings_grow(tiny_base):
    tokenizer = AutoTokenizer.from_pretrained(tiny_base)
    model = AutoModelForCausalLM.from_pretrained(tiny_base)
    before = len(tokenizer)
    assert add_special_tokens(tokenizer, model) == len(prompt.SPECIAL_TOKENS)
    assert model.get_input_embeddings().weight.shape[0] == len(tokenizer) == before + 10
    for marker in prompt.SPECIAL_TOKENS:
        assert len(tokenizer(marker, add_special_tokens=False)["input_ids"]) == 1
    assert tokenizer.pad_token is not None
    assert add_special_tokens(tokenizer, model) == 0  # adding again changes nothing


def test_only_the_target_is_learned(tiny_base):
    tokenizer = AutoTokenizer.from_pretrained(tiny_base)
    add_special_tokens(tokenizer)
    example = Example("c", "hint_level_1", "<|task|>hint_level_1\n<|response|>", "Look.<|end|>")
    encoded = encode(tokenizer, example, max_length=100)
    head = len(tokenizer(example.prompt, add_special_tokens=False)["input_ids"])
    assert encoded["labels"][:head] == [IGNORE] * head
    assert encoded["labels"][head:] == encoded["input_ids"][head:]
    assert encoded["input_ids"][-1] == tokenizer.convert_tokens_to_ids("<|end|>")
    assert encode(tokenizer, example, max_length=3) is None


def test_padding_is_masked_out_of_attention_and_loss():
    batch = collate(
        [{"input_ids": [5, 6, 7], "labels": [IGNORE, 6, 7]}, {"input_ids": [5], "labels": [5]}],
        pad_id=0,
    )
    assert batch["input_ids"].tolist() == [[5, 6, 7], [5, 0, 0]]
    assert batch["labels"].tolist() == [[IGNORE, 6, 7], [5, IGNORE, IGNORE]]
    assert batch["attention_mask"].tolist() == [[1, 1, 1], [1, 0, 0]]
