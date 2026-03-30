from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from turboquant_db.engine.query_plan import QueryPlan, build_query_plan
from turboquant_db.engine.query_stats import QueryStats, build_query_stats
from turboquant_db.engine.sealed_segments import SegmentReader
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase
from turboquant_db.filter_eval import build_filter_fn
from turboquant_db.filters import FilterIndexes, FilterPlanner, FilterStrategy, MetadataRow
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
    plan: QueryPlan
    stats: QueryStats


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

    def __init__(self, *args: Any, filter_planner: FilterPlanner | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.filter_planner = filter_planner or FilterPlanner()

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
        indexes = FilterIndexes(
            [
                *[MetadataRow(vector_id=row.vector_id, metadata=row.metadata) for row in mutable_rows],
                *[MetadataRow(vector_id=row.vector_id, metadata=row.metadata) for row in sealed_rows],
            ]
        )
        filter_plan = self.filter_planner.plan(filters=filters or {}, indexes=indexes)
        restricted_candidate_ids = filter_plan.candidate_ids if filter_plan.strategy == FilterStrategy.PRE_FILTER else None

        pre_filter_candidate_count = len(mutable_rows) + len(sealed_rows)
        filtered_mutable = [row for row in mutable_rows if filter_fn(row.metadata)]
        filtered_sealed = [row for row in sealed_rows if filter_fn(row.metadata)]
        post_filter_candidate_count = len(filtered_mutable) + len(filtered_sealed)

        plan = build_query_plan(
            top_k=top_k,
            approximate=approximate,
            rerank=rerank,
            filters_applied=bool(filters),
            filter_strategy=filter_plan.strategy.value,
            candidate_k=candidate_k,
        )

        search_start = perf_counter()
        mutable_search_filter = None if restricted_candidate_ids is not None else filter_fn
        sealed_search_filters = None if restricted_candidate_ids is not None else filters
        if approximate:
            mutable_candidates = self.query_executor.search_compressed(
                query_vector,
                top_k=len(mutable_rows),
                filter_fn=mutable_search_filter,
                candidate_ids=restricted_candidate_ids,
            )
            sealed_candidates = self._query_sealed_compressed(
                query_vector,
                top_k=len(sealed_rows),
                filters=sealed_search_filters,
                shard_id=shard_id,
                candidate_ids=restricted_candidate_ids,
            )
        else:
            mutable_candidates = self.query_executor.search_exact(
                query_vector,
                top_k=len(mutable_rows),
                filter_fn=mutable_search_filter,
                candidate_ids=restricted_candidate_ids,
            )
            sealed_candidates = self._query_sealed_exactish(
                query_vector,
                top_k=len(sealed_rows),
                filters=sealed_search_filters,
                shard_id=shard_id,
                candidate_ids=restricted_candidate_ids,
            )

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
        final_hits: list[Candidate]
        if rerank:
            rerank_start = perf_counter()
            rerank_candidate_ids = {candidate.vector_id for candidate in ranked[: plan.candidate_k or top_k]}
            rescored_mutable = self.query_executor.search_exact(
                query_vector,
                top_k=len(rerank_candidate_ids),
                candidate_ids=rerank_candidate_ids,
            )
            rescored_sealed = self._query_sealed_exactish(
                query_vector,
                top_k=len(rerank_candidate_ids),
                shard_id=shard_id,
                candidate_ids=rerank_candidate_ids,
            )
            rescored_merged: dict[str, Candidate] = {}
            for candidate in rescored_sealed:
                rescored_merged[candidate.vector_id] = candidate
                source_map[candidate.vector_id] = "sealed"
            for candidate in rescored_mutable:
                current = rescored_merged.get(candidate.vector_id)
                if current is None or candidate.score >= current.score:
                    rescored_merged[candidate.vector_id] = candidate
                    source_map[candidate.vector_id] = "mutable"
            final_hits = sorted(rescored_merged.values(), key=lambda item: item.score, reverse=True)[:top_k]
            rerank_latency_ms = (perf_counter() - rerank_start) * 1000.0
        else:
            final_hits = ranked[:top_k]

        stats = build_query_stats(
            result_ids=[hit.vector_id for hit in final_hits],
            source_by_vector_id=source_map,
            pre_filter_candidate_count=pre_filter_candidate_count,
            post_filter_candidate_count=post_filter_candidate_count,
        )
        total_latency_ms = (perf_counter() - total_start) * 1000.0

        inspection = QueryInspection(
            mode=f"{plan.mode}-engine",
            top_k=top_k,
            filters_applied=plan.filters_applied,
            mutable_live_count=len(mutable_rows),
            sealed_segment_count=len(sealed_segment_ids),
            sealed_segment_ids=sealed_segment_ids,
            result_count=len(final_hits),
            mutable_hit_count=stats.mutable_hit_count,
            sealed_hit_count=stats.sealed_hit_count,
            pre_filter_candidate_count=stats.pre_filter_candidate_count,
            post_filter_candidate_count=stats.post_filter_candidate_count,
            rerank_candidate_k=plan.candidate_k,
            search_latency_ms=search_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            total_latency_ms=total_latency_ms,
        )
        return QueryInspectionResult(hits=final_hits, inspection=inspection, plan=plan, stats=stats)
