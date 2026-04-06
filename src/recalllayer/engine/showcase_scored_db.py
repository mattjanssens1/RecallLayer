from __future__ import annotations

from time import perf_counter
from typing import Any

from recalllayer.engine.showcase_rerank_db import ShowcaseRerankDatabase
from recalllayer.retrieval.base import Candidate


class ShowcaseScoredDatabase(ShowcaseRerankDatabase):
    """Showcase database facade that returns rich scored hits."""

    def query_exact_hybrid_hits(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> list[Candidate]:
        ids = self.query_exact_hybrid(query_vector, top_k=top_k, filters=filters, shard_id=shard_id)
        return self._materialize_hits(ids=ids, query_vector=query_vector, shard_id=shard_id)

    def query_compressed_hybrid_hits(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
        search_budget: int | None = None,
    ) -> list[Candidate]:
        ids = self.query_compressed_hybrid(
            query_vector,
            top_k=top_k,
            filters=filters,
            shard_id=shard_id,
            search_budget=search_budget,
        )
        return self._materialize_hits(ids=ids, query_vector=query_vector, shard_id=shard_id)

    def query_compressed_reranked_hybrid_hits(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        candidate_k: int | None = None,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
        search_budget: int | None = None,
    ) -> list[Candidate]:
        ids = self.query_compressed_reranked_hybrid(
            query_vector,
            top_k=top_k,
            candidate_k=candidate_k,
            filters=filters,
            shard_id=shard_id,
            search_budget=search_budget,
        )
        return self._materialize_hits(ids=ids, query_vector=query_vector, shard_id=shard_id)

    def _materialize_hits(
        self,
        *,
        ids: list[str],
        query_vector: list[float],
        shard_id: str,
    ) -> list[Candidate]:
        materialize_start = perf_counter()
        sealed_vectors = self._sealed_vector_map(shard_id=shard_id)
        mutable_buffer = self._get_mutable_buffer(shard_id)
        hits: list[Candidate] = []
        for vector_id in ids:
            mutable_entry = mutable_buffer.get(vector_id)
            if (
                mutable_entry is not None
                and not mutable_entry.record.is_deleted
                and mutable_entry.embedding is not None
            ):
                vector = mutable_entry.embedding
                metadata = mutable_entry.metadata
            else:
                sealed_payload = sealed_vectors.get(vector_id)
                if sealed_payload is None:
                    continue
                vector, metadata = sealed_payload
            score = float(sum(a * b for a, b in zip(query_vector, vector, strict=True)))
            hits.append(Candidate(vector_id=vector_id, score=score, metadata=metadata))
        hits.sort(key=lambda item: item.score, reverse=True)
        trace = self.last_query_trace()
        trace["materialization_latency_ms"] = (perf_counter() - materialize_start) * 1000.0
        self._last_query_trace = trace
        return hits
