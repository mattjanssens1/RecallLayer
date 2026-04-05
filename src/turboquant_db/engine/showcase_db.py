from __future__ import annotations

from pathlib import Path
from typing import Any

from turboquant_db.engine.hybrid_core import HybridSearchInputs, run_hybrid_search
from turboquant_db.engine.local_db import LocalVectorDatabase
from turboquant_db.engine.sealed_segments import SegmentReader
from turboquant_db.filter_eval import build_filter_fn
from turboquant_db.retrieval.base import Candidate


class ShowcaseLocalDatabase(LocalVectorDatabase):
    """Higher-level local DB facade for demos, examples, and benchmark runs.

    Adds hybrid query behavior that merges mutable-buffer results with sealed
    segment results and applies exact metadata filters.
    """

    def _tombstoned_vector_ids(self) -> set[str]:
        return {
            vector_id
            for vector_id, entry in self.mutable_buffer._entries.items()
            if entry.record.is_deleted
        }

    def _segment_paths(self, *, shard_id: str = "shard-0") -> list[str]:
        shard_manifest = self.manifest_store.load(collection_id=self.collection_id, shard_id=shard_id)
        if shard_manifest is None or not shard_manifest.active_segment_ids:
            return [str(path) for path in self.segment_store.list_segment_files(collection_id=self.collection_id, shard_id=shard_id)]

        shard_dir = Path(self.segment_store.root_dir) / self.collection_id / shard_id
        paths: list[str] = []
        for segment_id in shard_manifest.active_segment_ids:
            path = shard_dir / f"{segment_id}.segment.jsonl"
            if path.exists():
                paths.append(str(path))
        return paths

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
        tombstoned_ids = self._tombstoned_vector_ids()
        candidates: list[Candidate] = []
        for path in self._segment_paths(shard_id=shard_id):
            reader = SegmentReader(path)
            for indexed in reader.iter_indexed_vectors():
                if indexed.vector_id in tombstoned_ids:
                    continue
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
        tombstoned_ids = self._tombstoned_vector_ids()
        candidates: list[Candidate] = []
        for path in self._segment_paths(shard_id=shard_id):
            reader = SegmentReader(path)
            for indexed in reader.iter_indexed_vectors():
                if indexed.vector_id in tombstoned_ids:
                    continue
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
        result = run_hybrid_search(
            inputs=HybridSearchInputs(query_vector=query_vector, top_k=top_k, filters=filters),
            mutable_search=lambda vector, limit, filter_fn, candidate_ids: self.query_executor.search_exact(
                vector,
                top_k=limit,
                filter_fn=filter_fn,
                candidate_ids=candidate_ids,
            ),
            sealed_search=lambda vector, limit, sealed_filters, candidate_ids: self._query_sealed_exactish(
                vector,
                top_k=limit,
                filters=sealed_filters,
                shard_id=shard_id,
                candidate_ids=candidate_ids,
            ),
            mode="exact",
        )
        return [item.vector_id for item in result.ranked_hits]

    def query_compressed_hybrid(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> list[str]:
        result = run_hybrid_search(
            inputs=HybridSearchInputs(query_vector=query_vector, top_k=top_k, filters=filters),
            mutable_search=lambda vector, limit, filter_fn, candidate_ids: self.query_executor.search_compressed(
                vector,
                top_k=limit,
                filter_fn=filter_fn,
                candidate_ids=candidate_ids,
            ),
            sealed_search=lambda vector, limit, sealed_filters, candidate_ids: self._query_sealed_compressed(
                vector,
                top_k=limit,
                filters=sealed_filters,
                shard_id=shard_id,
                candidate_ids=candidate_ids,
            ),
            mode="compressed",
        )
        return [item.vector_id for item in result.ranked_hits]
