from __future__ import annotations

from typing import Any, Callable

from recalllayer.engine.mutable_buffer import MutableBuffer
from recalllayer.quantization.base import Quantizer
from recalllayer.retrieval.base import Candidate, IndexedVector
from recalllayer.retrieval.exact import ExactRetriever
from recalllayer.retrieval.scan import CompressedScanRetriever


FilterFn = Callable[[dict[str, Any]], bool]


class QueryExecutor:
    """Prototype query executor over the mutable buffer.

    This is intentionally simple: it can execute either exact full-precision search
    or compressed scan retrieval over the current live mutable state.
    """

    def __init__(self, *, mutable_buffer: MutableBuffer, quantizer: Quantizer | None = None) -> None:
        self.mutable_buffer = mutable_buffer
        self.quantizer = quantizer

    def search_exact(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filter_fn: FilterFn | None = None,
        candidate_ids: set[str] | None = None,
    ) -> list[Candidate]:
        if candidate_ids is not None and not candidate_ids:
            return []

        retriever = ExactRetriever()
        for entry in self.mutable_buffer.live_entries():
            if entry.embedding is None:
                continue
            if candidate_ids is not None and entry.record.vector_id not in candidate_ids:
                continue
            retriever.add(
                vector_id=entry.record.vector_id,
                values=entry.embedding,
                metadata=entry.metadata,
            )
        return retriever.search(query_vector=query_vector, top_k=top_k, filter_fn=filter_fn)

    def search_compressed(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filter_fn: FilterFn | None = None,
        candidate_ids: set[str] | None = None,
    ) -> list[Candidate]:
        if self.quantizer is None:
            raise ValueError("quantizer is required for compressed search")
        if candidate_ids is not None and not candidate_ids:
            return []

        retriever = CompressedScanRetriever(quantizer=self.quantizer)
        for entry in self.mutable_buffer.live_entries():
            if entry.embedding is None:
                continue
            if candidate_ids is not None and entry.record.vector_id not in candidate_ids:
                continue
            retriever.add(
                IndexedVector(
                    vector_id=entry.record.vector_id,
                    encoded=self.quantizer.encode(entry.embedding),
                    metadata=entry.metadata,
                )
            )
        return retriever.search(query_vector=query_vector, top_k=top_k, filter_fn=filter_fn)
