from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from recalllayer.retrieval.base import Candidate


FilterFn = Callable[[dict[str, Any]], bool]


@dataclass(slots=True)
class ExactVector:
    vector_id: str
    values: np.ndarray
    metadata: dict[str, Any]


class ExactRetriever:
    """Ground-truth or baseline retriever over full-precision vectors."""

    def __init__(self, vectors: Iterable[ExactVector] | None = None) -> None:
        self.name = "exact"
        self._vectors = list(vectors or [])

    def add(self, vector_id: str, values: Sequence[float], metadata: dict[str, Any] | None = None) -> None:
        self._vectors.append(
            ExactVector(
                vector_id=vector_id,
                values=np.asarray(values, dtype=np.float32),
                metadata=metadata or {},
            )
        )

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int,
        filter_fn: FilterFn | None = None,
    ) -> list[Candidate]:
        if top_k <= 0:
            return []

        query = np.asarray(query_vector, dtype=np.float32)
        heap: list[tuple[float, str, dict[str, Any]]] = []
        for vector in self._vectors:
            if filter_fn is not None and not filter_fn(vector.metadata):
                continue
            score = float(np.dot(query, vector.values))
            item = (score, vector.vector_id, vector.metadata)
            if len(heap) < top_k:
                heapq.heappush(heap, item)
            else:
                heapq.heappushpop(heap, item)

        ranked = sorted(heap, key=lambda row: row[0], reverse=True)
        return [Candidate(vector_id=vector_id, score=score, metadata=metadata) for score, vector_id, metadata in ranked]
