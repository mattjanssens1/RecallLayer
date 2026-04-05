from __future__ import annotations

from pathlib import Path
from typing import Any

from recalllayer.engine.hybrid_core import HybridSearchInputs, run_hybrid_search
from recalllayer.engine.local_db import LocalVectorDatabase
from recalllayer.engine.sealed_segments import SegmentReader
from recalllayer.filter_eval import build_filter_fn
from recalllayer.retrieval.base import Candidate


class ShowcaseLocalDatabase(LocalVectorDatabase):
    """Higher-level local DB facade for demos, examples, and benchmark runs.

    Adds hybrid query behavior that merges mutable-buffer results with sealed
    segment results and applies exact metadata filters.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_query_trace: dict[str, Any] = {}

    def last_query_trace(self) -> dict[str, Any]:
        return dict(self._last_query_trace)

    def _tombstoned_vector_ids(self) -> set[str]:
        return {
            vector_id
            for vector_id, entry in self.mutable_buffer._entries.items()
            if entry.record.is_deleted
        }

    def _segment_paths(self, *, shard_id: str = "shard-0") -> list[str]:
        shard_manifest = self.manifest_store.load(
            collection_id=self.collection_id, shard_id=shard_id
        )
        if shard_manifest is None or not shard_manifest.active_segment_ids:
            return [
                str(path)
                for path in self.segment_store.list_segment_files(
                    collection_id=self.collection_id, shard_id=shard_id
                )
            ]

        shard_dir = Path(self.segment_store.root_dir) / self.collection_id / shard_id
        paths: list[str] = []
        for segment_id in shard_manifest.active_segment_ids:
            path = shard_dir / f"{segment_id}.segment.jsonl"
            if path.exists():
                paths.append(str(path))
        return paths

    def _query_snapshot(self, *, shard_id: str = "shard-0") -> tuple[list[str], int]:
        """Capture a stable read snapshot at query entry.

        Returns (segment_paths, mutable_watermark) captured atomically so that
        concurrent manifest changes do not affect an in-flight query.
        """
        segment_paths = self._segment_paths(shard_id=shard_id)
        mutable_watermark = self.mutable_buffer.watermark()
        return segment_paths, mutable_watermark

    def _query_sealed_exactish(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
        candidate_ids: set[str] | None = None,
        snapshot_paths: list[str] | None = None,
    ) -> list[Candidate]:
        if candidate_ids is not None and not candidate_ids:
            return []

        filter_fn = build_filter_fn(filters or {})
        tombstoned_ids = self._tombstoned_vector_ids()
        candidates: list[Candidate] = []
        paths = (
            snapshot_paths if snapshot_paths is not None else self._segment_paths(shard_id=shard_id)
        )
        for path in paths:
            for vector_id, reconstructed, metadata in self._decoded_segment_payloads([path]):
                if vector_id in tombstoned_ids:
                    continue
                if candidate_ids is not None and vector_id not in candidate_ids:
                    continue
                if not filter_fn(metadata):
                    continue
                score = float(sum(a * b for a, b in zip(query_vector, reconstructed, strict=True)))
                candidates.append(Candidate(vector_id=vector_id, score=score, metadata=metadata))
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
        snapshot_paths: list[str] | None = None,
    ) -> list[Candidate]:
        if candidate_ids is not None and not candidate_ids:
            return []

        filter_fn = build_filter_fn(filters or {})
        tombstoned_ids = self._tombstoned_vector_ids()
        candidates: list[Candidate] = []
        paths = (
            snapshot_paths if snapshot_paths is not None else self._segment_paths(shard_id=shard_id)
        )
        for path in paths:
            reader = SegmentReader(
                path,
                cache=self.segment_cache if self.enable_segment_cache else None,
                read_stats=self.segment_read_stats,
            )
            for indexed in reader.iter_indexed_vectors():
                if indexed.vector_id in tombstoned_ids:
                    continue
                if candidate_ids is not None and indexed.vector_id not in candidate_ids:
                    continue
                if not filter_fn(indexed.metadata):
                    continue
                score = self.quantizer.approx_score(
                    query_vector=query_vector, encoded=indexed.encoded
                )
                candidates.append(
                    Candidate(vector_id=indexed.vector_id, score=score, metadata=indexed.metadata)
                )
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_k]

    def _decoded_segment_payloads(
        self,
        paths: list[str],
    ) -> list[tuple[str, Any, dict[str, Any]]]:
        payloads: list[tuple[str, Any, dict[str, Any]]] = []
        for path in paths:
            cached = self.decoded_segment_cache.get(path) if self.enable_segment_cache else None
            if cached is not None:
                payloads.extend(cached)
                continue
            reader = SegmentReader(
                path,
                cache=self.segment_cache if self.enable_segment_cache else None,
                read_stats=self.segment_read_stats,
            )
            decoded_rows: list[tuple[str, Any, dict[str, Any]]] = []
            for indexed in reader.iter_indexed_vectors():
                decoded_rows.append(
                    (
                        indexed.vector_id,
                        (indexed.encoded.codes.astype("float32") * indexed.encoded.scale).tolist(),
                        indexed.metadata,
                    )
                )
            if self.enable_segment_cache:
                self.decoded_segment_cache.put(path, decoded_rows)
            payloads.extend(decoded_rows)
        return payloads

    def _record_hybrid_trace(
        self, *, mode: str, result: Any, top_k: int, filters: dict[str, Any] | None
    ) -> None:
        self._last_query_trace = {
            "mode": mode,
            "top_k": top_k,
            "filters_applied": bool(filters),
            "candidate_generation_count": len(result.mutable_candidates)
            + len(result.sealed_candidates),
            "mutable_candidate_count": len(result.mutable_candidates),
            "sealed_candidate_count": len(result.sealed_candidates),
            "result_count": len(result.ranked_hits),
            "rerank_candidate_count": None,
            "mutable_search_latency_ms": result.mutable_search_latency_ms,
            "sealed_search_latency_ms": result.sealed_search_latency_ms,
            "merge_latency_ms": result.merge_latency_ms,
            "rerank_latency_ms": 0.0,
            "materialization_latency_ms": 0.0,
        }

    def query_exact_hybrid(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> list[str]:
        # Capture stable snapshot at query entry
        snapshot_paths, _watermark = self._query_snapshot(shard_id=shard_id)
        result = run_hybrid_search(
            inputs=HybridSearchInputs(query_vector=query_vector, top_k=top_k, filters=filters),
            mutable_search=lambda vector, limit, filter_fn, candidate_ids: (
                self.query_executor.search_exact(
                    vector,
                    top_k=limit,
                    filter_fn=filter_fn,
                    candidate_ids=candidate_ids,
                )
            ),
            sealed_search=lambda vector, limit, sealed_filters, candidate_ids: (
                self._query_sealed_exactish(
                    vector,
                    top_k=limit,
                    filters=sealed_filters,
                    shard_id=shard_id,
                    candidate_ids=candidate_ids,
                    snapshot_paths=snapshot_paths,
                )
            ),
            mode="exact",
        )
        self._record_hybrid_trace(mode="exact-hybrid", result=result, top_k=top_k, filters=filters)
        return [item.vector_id for item in result.ranked_hits]

    def query_compressed_hybrid(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> list[str]:
        # Capture stable snapshot at query entry
        snapshot_paths, _watermark = self._query_snapshot(shard_id=shard_id)
        result = run_hybrid_search(
            inputs=HybridSearchInputs(query_vector=query_vector, top_k=top_k, filters=filters),
            mutable_search=lambda vector, limit, filter_fn, candidate_ids: (
                self.query_executor.search_compressed(
                    vector,
                    top_k=limit,
                    filter_fn=filter_fn,
                    candidate_ids=candidate_ids,
                )
            ),
            sealed_search=lambda vector, limit, sealed_filters, candidate_ids: (
                self._query_sealed_compressed(
                    vector,
                    top_k=limit,
                    filters=sealed_filters,
                    shard_id=shard_id,
                    candidate_ids=candidate_ids,
                    snapshot_paths=snapshot_paths,
                )
            ),
            mode="compressed",
        )
        self._record_hybrid_trace(
            mode="compressed-hybrid", result=result, top_k=top_k, filters=filters
        )
        return [item.vector_id for item in result.ranked_hits]
