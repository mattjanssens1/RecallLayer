from __future__ import annotations

from typing import Any

from turboquant_db.engine.hybrid_core import rerank_hybrid_candidates
from turboquant_db.engine.showcase_db import ShowcaseLocalDatabase
from turboquant_db.engine.sealed_segments import SegmentReader


class ShowcaseRerankDatabase(ShowcaseLocalDatabase):
    """Showcase facade with a simple rerank stage for hybrid compressed queries."""

    def _sealed_vector_map(self, *, shard_id: str = "shard-0") -> dict[str, tuple[list[float], dict[str, Any]]]:
        vectors: dict[str, tuple[list[float], dict[str, Any]]] = {}
        for path in self._segment_paths(shard_id=shard_id):
            reader = SegmentReader(path)
            for indexed in reader.iter_indexed_vectors():
                reconstructed = (indexed.encoded.codes.astype("float32") * indexed.encoded.scale).tolist()
                vectors[indexed.vector_id] = (reconstructed, indexed.metadata)
        return vectors

    def query_compressed_reranked_hybrid(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        candidate_k: int | None = None,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> list[str]:
        candidate_k = max(candidate_k or (top_k * 4), top_k)
        candidate_ids = self.query_compressed_hybrid(
            query_vector,
            top_k=candidate_k,
            filters=filters,
            shard_id=shard_id,
        )
        reranked = rerank_hybrid_candidates(
            candidate_ids=candidate_ids,
            top_k=top_k,
            mutable_exact_search=lambda vector, limit, filter_fn, restricted_ids: self.query_executor.search_exact(
                vector,
                top_k=limit,
                filter_fn=filter_fn,
                candidate_ids=restricted_ids,
            ),
            sealed_exact_search=lambda vector, limit, sealed_filters, restricted_ids: self._query_sealed_exactish(
                vector,
                top_k=limit,
                filters=sealed_filters,
                shard_id=shard_id,
                candidate_ids=restricted_ids,
            ),
            query_vector=query_vector,
        )
        return [candidate.vector_id for candidate in reranked.final_hits]
