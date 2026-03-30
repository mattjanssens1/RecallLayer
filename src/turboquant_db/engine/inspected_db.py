from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from turboquant_db.engine.sealed_segments import SegmentReader
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase
from turboquant_db.filter_eval import build_filter_fn
from turboquant_db.retrieval.base import Candidate


@dataclass(slots=True)
class QueryInspection:
    mode: str
    top_k: int
    filters_applied: bool
    mutable_live_count: int
    sealed_segment_count: int
    sealed_segment_ids: list[str]
    result_count: int
    mutable_hit_count: int
    sealed_hit_count: int
    pre_filter_candidate_count: int
    post_filter_candidate_count: int
    rerank_candidate_k: int | None
    search_latency_ms: float
    rerank_latency_ms: float
    total_latency_ms: float


@dataclass(slots=True)
class QueryInspectionResult:
    hits: list[Candidate]
    inspection: QueryInspection


@dataclass(slots=True)
class _MutableRow:
    vector_id: str
    embedding: list[float]
    metadata: dict[str, Any]


@dataclass(slots=True)
class _SealedRow:
    vector_id: str
    reconstructed: list[float]
    metadata: dict[str, Any]
    encoded: Any


class InspectedShowcaseDatabase(ShowcaseScoredDatabase):
    """Engine-facing facade that computes real hybrid query breakdowns."""

    def _collect_mutable_rows(self) -> list[_MutableRow]:
        rows: list[_MutableRow] = []
        for entry in self.mutable_buffer.live_entries():
            if entry.embedding is None:
                continue
            rows.append(
                _MutableRow(
                    vector_id=entry.record.vector_id,
                    embedding=entry.embedding,
                    metadata=entry.metadata,
                )
            )
        return rows

    def _collect_sealed_rows(self, *, shard_id: str) -> tuple[list[str], list[_SealedRow]]:
        paths = self._segment_paths(shard_id=shard_id)
        rows: list[_SealedRow] = []
        for path in paths:
            reader = SegmentReader(path)
            for indexed in reader.iter_indexed_vectors():
                reconstructed = (indexed.encoded.codes.astype("float32") * indexed.encoded.scale).tolist()
                rows.append(
                    _SealedRow(
                        vector_id=indexed.vector_id,
                        reconstructed=reconstructed,
                        metadata=indexed.metadata,
                        encoded=indexed.encoded,
                    )
                )
        return [path.split("/")[-1] for path in paths], rows

    def query_exact_hybrid_inspected(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> QueryInspectionResult:
        return self._query_inspected(
            mode="exact-hybrid-engine",
            query_vector=query_vector,
            top_k=top_k,
            filters=filters,
            shard_id=shard_id,
            approximate=False,
            rerank=False,
        )

    def query_compressed_hybrid_inspected(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> QueryInspectionResult:
        return self._query_inspected(
            mode="compressed-hybrid-engine",
            query_vector=query_vector,
            top_k=top_k,
            filters=filters,
            shard_id=shard_id,
            approximate=True,
            rerank=False,
        )

    def query_compressed_reranked_hybrid_inspected(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        candidate_k: int | None = None,
        filters: dict[str, Any] | None = None,
        shard_id: str = "shard-0",
    ) -> QueryInspectionResult:
        return self._query_inspected(
            mode="compressed-reranked-hybrid-engine",
            query_vector=query_vector,
            top_k=top_k,
            filters=filters,
            shard_id=shard_id,
            approximate=True,
            rerank=True,
            candidate_k=candidate_k,
        )

    def _query_inspected(
        self,
        *,
        mode: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None,
        shard_id: str,
        approximate: bool,
        rerank: bool,
        candidate_k: int | None = None,
    ) -> QueryInspectionResult:
        total_start = perf_counter()
        filter_fn = build_filter_fn(filters or {})

        mutable_rows = self._collect_mutable_rows()
        sealed_segment_ids, sealed_rows = self._collect_sealed_rows(shard_id=shard_id)

        pre_filter_candidate_count = len(mutable_rows) + len(sealed_rows)
        filtered_mutable = [row for row in mutable_rows if filter_fn(row.metadata)]
        filtered_sealed = [row for row in sealed_rows if filter_fn(row.metadata)]
        post_filter_candidate_count = len(filtered_mutable) + len(filtered_sealed)

        search_start = perf_counter()
        if approximate:
            mutable_candidates = [
                Candidate(
                    vector_id=row.vector_id,
                    score=float(self.quantizer.approx_score(query_vector, self.quantizer.encode(row.embedding))),
                    metadata=row.metadata,
                )
                for row in filtered_mutable
            ]
            sealed_candidates = [
                Candidate(
                    vector_id=row.vector_id,
                    score=float(self.quantizer.approx_score(query_vector, row.encoded)),
                    metadata=row.metadata,
                )
                for row in filtered_sealed
            ]
        else:
            mutable_candidates = [
                Candidate(
                    vector_id=row.vector_id,
                    score=float(sum(a * b for a, b in zip(query_vector, row.embedding))),
                    metadata=row.metadata,
                )
                for row in filtered_mutable
            ]
            sealed_candidates = [
                Candidate(
                    vector_id=row.vector_id,
                    score=float(sum(a * b for a, b in zip(query_vector, row.reconstructed))),
                    metadata=row.metadata,
                )
                for row in filtered_sealed
            ]

        merged: dict[str, Candidate] = {}
        source_map: dict[str, str] = {}
        for candidate in sealed_candidates:
            merged[candidate.vector_id] = candidate
            source_map[candidate.vector_id] = "sealed"
        for candidate in mutable_candidates:
            current = merged.get(candidate.vector_id)
            if current is None or candidate.score >= current.score:
                merged[candidate.vector_id] = candidate
                source_map[candidate.vector_id] = "mutable"

        ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        search_latency_ms = (perf_counter() - search_start) * 1000.0

        rerank_latency_ms = 0.0
        rerank_candidate_k = None
        final_hits: list[Candidate]
        if rerank:
            rerank_candidate_k = max(candidate_k or (top_k * 4), top_k)
            rerank_start = perf_counter()
            candidate_ids = [candidate.vector_id for candidate in ranked[:rerank_candidate_k]]
            mutable_lookup = {row.vector_id: row for row in filtered_mutable}
            sealed_lookup = {row.vector_id: row for row in filtered_sealed}
            rescored: list[Candidate] = []
            for vector_id in candidate_ids:
                mutable_row = mutable_lookup.get(vector_id)
                if mutable_row is not None:
                    score = float(sum(a * b for a, b in zip(query_vector, mutable_row.embedding)))
                    rescored.append(Candidate(vector_id=vector_id, score=score, metadata=mutable_row.metadata))
                    source_map[vector_id] = "mutable"
                    continue
                sealed_row = sealed_lookup.get(vector_id)
                if sealed_row is None:
                    continue
                score = float(sum(a * b for a, b in zip(query_vector, sealed_row.reconstructed)))
                rescored.append(Candidate(vector_id=vector_id, score=score, metadata=sealed_row.metadata))
                source_map[vector_id] = "sealed"
            rescored.sort(key=lambda item: item.score, reverse=True)
            final_hits = rescored[:top_k]
            rerank_latency_ms = (perf_counter() - rerank_start) * 1000.0
        else:
            final_hits = ranked[:top_k]

        mutable_hit_count = sum(1 for hit in final_hits if source_map.get(hit.vector_id) == "mutable")
        sealed_hit_count = sum(1 for hit in final_hits if source_map.get(hit.vector_id) == "sealed")
        total_latency_ms = (perf_counter() - total_start) * 1000.0

        inspection = QueryInspection(
            mode=mode,
            top_k=top_k,
            filters_applied=bool(filters),
            mutable_live_count=len(mutable_rows),
            sealed_segment_count=len(sealed_segment_ids),
            sealed_segment_ids=sealed_segment_ids,
            result_count=len(final_hits),
            mutable_hit_count=mutable_hit_count,
            sealed_hit_count=sealed_hit_count,
            pre_filter_candidate_count=pre_filter_candidate_count,
            post_filter_candidate_count=post_filter_candidate_count,
            rerank_candidate_k=rerank_candidate_k,
            search_latency_ms=search_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            total_latency_ms=total_latency_ms,
        )
        return QueryInspectionResult(hits=final_hits, inspection=inspection)
