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


def mean_recall_at_k(
    *,
    expected_per_query: Sequence[Sequence[str]],
    actual_per_query: Sequence[Sequence[str]],
    k: int,
) -> float:
    if k <= 0:
        return 0.0
    if len(expected_per_query) != len(actual_per_query):
        raise ValueError("expected_per_query and actual_per_query must have the same length")
    if not expected_per_query:
        return 1.0
    return float(
        mean(
            recall_at_k(expected_ids=expected_ids, actual_ids=actual_ids, k=k)
            for expected_ids, actual_ids in zip(expected_per_query, actual_per_query, strict=True)
        )
    )


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
