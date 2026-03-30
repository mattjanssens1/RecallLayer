from __future__ import annotations

from typing import Any

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

        sealed_vectors = self._sealed_vector_map(shard_id=shard_id)
        scored: list[tuple[float, str]] = []
        for vector_id in candidate_ids:
            mutable_entry = self.mutable_buffer.get(vector_id)
            if mutable_entry is not None and not mutable_entry.record.is_deleted and mutable_entry.embedding is not None:
                vector = mutable_entry.embedding
            else:
                sealed_payload = sealed_vectors.get(vector_id)
                if sealed_payload is None:
                    continue
                vector = sealed_payload[0]
            score = float(sum(a * b for a, b in zip(query_vector, vector)))
            scored.append((score, vector_id))

        scored.sort(reverse=True)
        return [vector_id for _score, vector_id in scored[:top_k]]
