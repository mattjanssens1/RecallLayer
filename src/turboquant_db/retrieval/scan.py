from __future__ import annotations

import heapq
from typing import Iterable

from turboquant_db.quantization.base import Quantizer
from turboquant_db.retrieval.base import Candidate, FilterFn, IndexedVector


class CompressedScanRetriever:
    """Simple top-k retriever over quantized in-memory vectors."""

    def __init__(self, *, quantizer: Quantizer, indexed_vectors: Iterable[IndexedVector] | None = None) -> None:
        self.quantizer = quantizer
        self.name = f"scan/{getattr(quantizer, 'name', quantizer.__class__.__name__)}"
        self._indexed_vectors = list(indexed_vectors or [])

    def add(self, indexed_vector: IndexedVector) -> None:
        self._indexed_vectors.append(indexed_vector)

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filter_fn: FilterFn | None = None,
    ) -> list[Candidate]:
        if top_k <= 0:
            return []

        heap: list[tuple[float, str, dict[str, object]]] = []
        for indexed in self._indexed_vectors:
            if filter_fn is not None and not filter_fn(indexed.metadata):
                continue

            score = self.quantizer.approx_score(query_vector=query_vector, encoded=indexed.encoded)
            item = (score, indexed.vector_id, indexed.metadata)
            if len(heap) < top_k:
                heapq.heappush(heap, item)
            else:
                heapq.heappushpop(heap, item)

        ranked = sorted(heap, key=lambda row: row[0], reverse=True)
        return [Candidate(vector_id=vector_id, score=score, metadata=metadata) for score, vector_id, metadata in ranked]
