from __future__ import annotations

from collections.abc import Sequence
from statistics import mean


def recall_at_k(*, expected_ids: Sequence[str], actual_ids: Sequence[str], k: int) -> float:
    if k <= 0:
        return 0.0
    expected = list(expected_ids[:k])
    actual = set(actual_ids[:k])
    if not expected:
        return 1.0
    hits = sum(1 for value in expected if value in actual)
    return hits / float(len(expected))


def top_k_overlap(*, left_ids: Sequence[str], right_ids: Sequence[str], k: int) -> float:
    if k <= 0:
        return 0.0
    left = set(left_ids[:k])
    right = set(right_ids[:k])
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / float(len(union))


def average_latency_ms(samples_ms: Sequence[float]) -> float:
    if not samples_ms:
        return 0.0
    return float(mean(samples_ms))
