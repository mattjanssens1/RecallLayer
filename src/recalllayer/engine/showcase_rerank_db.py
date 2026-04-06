from __future__ import annotations

from typing import Any

from recalllayer.engine.hybrid_core import rerank_hybrid_candidates
from recalllayer.engine.showcase_db import ShowcaseLocalDatabase


class ShowcaseRerankDatabase(ShowcaseLocalDatabase):
    """Showcase facade with a simple rerank stage for hybrid compressed queries.

    ``rerank_probe_k`` sets the IVF probe width used only during candidate
    generation for the reranked path.  A higher value yields better recall at
    the cost of scoring more vectors before the exact rerank step.  Defaults to
    ``ivf_probe_k * 2`` (capped to the total cluster count at query time).
    """

    def __init__(self, *args: Any, rerank_probe_k: int | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rerank_probe_k = rerank_probe_k

    def _sealed_vector_map(
        self, *, shard_id: str = "shard-0"
    ) -> dict[str, tuple[list[float], dict[str, Any]]]:
        vectors: dict[str, tuple[list[float], dict[str, Any]]] = {}
        for vector_id, reconstructed, metadata in self._decoded_segment_payloads(
            self._segment_paths(shard_id=shard_id)
        ):
            vectors[vector_id] = (reconstructed, metadata)
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
        # Use a wider IVF probe for candidate generation so the reranker has
        # enough true neighbours to choose from.  Fall back to ivf_probe_k*2.
        probe_k = self._rerank_probe_k if self._rerank_probe_k is not None else self.ivf_probe_k * 2
        candidate_ids = self.query_compressed_hybrid(
            query_vector,
            top_k=candidate_k,
            filters=filters,
            shard_id=shard_id,
            probe_k=probe_k,
        )
        reranked = rerank_hybrid_candidates(
            candidate_ids=candidate_ids,
            top_k=top_k,
            mutable_exact_search=lambda vector, limit, filter_fn, restricted_ids: (
                self.query_executor.search_exact(
                    vector,
                    top_k=limit,
                    filter_fn=filter_fn,
                    candidate_ids=restricted_ids,
                )
            ),
            sealed_exact_search=lambda vector, limit, sealed_filters, restricted_ids: (
                self._query_sealed_exactish(
                    vector,
                    top_k=limit,
                    filters=sealed_filters,
                    shard_id=shard_id,
                    candidate_ids=restricted_ids,
                )
            ),
            query_vector=query_vector,
        )
        trace = self.last_query_trace()
        trace["mode"] = "compressed-reranked-hybrid"
        trace["rerank_candidate_count"] = len(candidate_ids)
        trace["rerank_latency_ms"] = reranked.rerank_latency_ms
        trace["result_count"] = len(reranked.final_hits)
        self._last_query_trace = trace
        return [candidate.vector_id for candidate in reranked.final_hits]
