"""Student-facing starter: complete masked attention weight computation."""
from collections.abc import Sequence


def masked_attention_weights(logits: Sequence[Sequence[float]], allowed: Sequence[Sequence[bool]]) -> list[list[float]]:
    """Normalize permitted scores row-wise; masked entries must be exactly zero."""
    raise NotImplementedError("implement the stable row-wise masked softmax")
