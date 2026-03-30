from __future__ import annotations

from pathlib import Path
from typing import Any

from turboquant_db.engine.local_db import LocalVectorDatabase
from turboquant_db.engine.sealed_segments import SegmentReader
from turboquant_db.filter_eval import build_filter_fn
from turboquant_db.retrieval.base import Candidate


class ShowcaseLocalDatabase(LocalVectorDatabase):
    """Higher-level local DB facade for demos, examples, and benchmark runs.

    Adds hybrid query behavior that merges mutable-buffer results with sealed
    segment results and applies exact metadata filters.
    """

    def _segment_paths(self, *, shard_id: str = "shard-0") -> list[str]:
        return [str(path) for path in self.segment_store.list_segment_files(collection_id=self.collection_id, shard_id=shard_id)]

    def _query_sealed_exactish(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
        candidate_ids: set[str] | None = None,
    ) -> list[Candidate]:
        if candidate_ids is not None and not candidate_ids:
            return []

        filter_fn = build_filter_fn(filters or {})
        candidates: list[Candidate] = []
        for path in self._segment_paths(shard_id=shard_id):
            reader = SegmentReader(path)
            for indexed in reader.iter_indexed_vectors():
                if candidate_ids is not None and indexed.vector_id not in candidate_ids:
                    continue
                if not filter_fn(indexed.metadata):
                    continue
                reconstructed = indexed.encoded.codes.astype("float32") * indexed.encoded.scale
                score = float(sum(a * b for a, b in zip(query_vector, reconstructed.tolist())))
                candidates.append(Candidate(vector_id=indexed.vector_id, score=score, metadata=indexed.metadata))
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_k]

    def _query_sealed_compressed(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
        candidate_ids: set[str] | None = None,
    ) -> list[Candidate]:
        if candidate_ids is not None and not candidate_ids:
            return []

        filter_fn = build_filter_fn(filters or {})
        candidates: list[Candidate] = []
        for path in self._segment_paths(shard_id=shard_id):
            reader = SegmentReader(path)
            for indexed in reader.iter_indexed_vectors():
                if candidate_ids is not None and indexed.vector_id not in candidate_ids:
                    continue
                if not filter_fn(indexed.metadata):
                    continue
                score = self.quantizer.approx_score(query_vector=query_vector, encoded=indexed.encoded)
                candidates.append(Candidate(vector_id=indexed.vector_id, score=score, metadata=indexed.metadata))
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_k]

    def query_exact_hybrid(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> list[str]:
        filter_fn = build_filter_fn(filters or {})
        mutable = self.query_executor.search_exact(query_vector, top_k=top_k, filter_fn=filter_fn)
        sealed = self._query_sealed_exactish(query_vector, top_k=top_k, filters=filters, shard_id=shard_id)
        merged: dict[str, Candidate] = {}
        for candidate in [*mutable, *sealed]:
            current = merged.get(candidate.vector_id)
            if current is None or candidate.score > current.score:
                merged[candidate.vector_id] = candidate
        ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        return [item.vector_id for item in ranked[:top_k]]

    def query_compressed_hybrid(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> list[str]:
        filter_fn = build_filter_fn(filters or {})
        mutable = self.query_executor.search_compressed(query_vector, top_k=top_k, filter_fn=filter_fn)
        sealed = self._query_sealed_compressed(query_vector, top_k=top_k, filters=filters, shard_id=shard_id)
        merged: dict[str, Candidate] = {}
        for candidate in [*mutable, *sealed]:
            current = merged.get(candidate.vector_id)
            if current is None or candidate.score > current.score:
                merged[candidate.vector_id] = candidate
        ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        return [item.vector_id for item in ranked[:top_k]]
