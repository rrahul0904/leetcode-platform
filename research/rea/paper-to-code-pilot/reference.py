"""Independently authored CPU-only reference for a masked attention softmax.

This is a learning micro-kernel, not a complete attention layer or code sandbox.
"""
from __future__ import annotations

from math import exp, fsum, isfinite
from collections.abc import Sequence


def masked_attention_weights(
    logits: Sequence[Sequence[float]],
    allowed: Sequence[Sequence[bool]],
) -> list[list[float]]:
    """Return normalized row-wise attention weights for explicitly permitted keys.

    Invalid row shapes, non-finite input scores, or rows with no permitted key
    raise ValueError rather than producing a misleading probability vector.
    """
    if len(logits) != len(allowed):
        raise ValueError("mask and scores must have the same row count")

    weights: list[list[float]] = []
    for score_row, mask_row in zip(logits, allowed, strict=True):
        if not score_row or len(score_row) != len(mask_row):
            raise ValueError("each score row must be nonempty and match its mask")
        if any(type(flag) is not bool for flag in mask_row):
            raise ValueError("mask elements must be booleans")
        if any(not isfinite(value) for value in score_row):
            raise ValueError("scores must be finite")
        valid_scores = [float(score) for score, flag in zip(score_row, mask_row, strict=True) if flag]
        if not valid_scores:
            raise ValueError("every row needs at least one permitted key")
        shift = max(valid_scores)
        unnormalized = [
            exp(score - shift) if flag else 0.0
            for score, flag in zip(score_row, mask_row, strict=True)
        ]
        divisor = fsum(unnormalized)
        weights.append([value / divisor for value in unnormalized])
    return weights
