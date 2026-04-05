from __future__ import annotations

from typing import Any

from turboquant_db.api.schemas import QueryRequest
from turboquant_db.api.showcase_notes import build_collection_notes
from turboquant_db.api.showcase_query_api import build_mode_name


class InspectedSurfaceRunner:
    def __init__(self, *, db: Any) -> None:
        self.db = db

    def execute(self, request: QueryRequest):
        if request.approximate and request.rerank:
            return self.db.query_compressed_reranked_hybrid_inspected(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
        if request.approximate:
            return self.db.query_compressed_hybrid_inspected(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
        return self.db.query_exact_hybrid_inspected(
            request.embedding,
            top_k=request.top_k,
            filters=request.filters,
        )


def build_inspected_trace_payload(*, request: QueryRequest, result: Any, collection_id: str) -> dict[str, Any]:
    inspection = result.inspection
    return {
        "mode": inspection.mode,
        "top_k": inspection.top_k,
        "filters_applied": inspection.filters_applied,
        "mutable_live_count": inspection.mutable_live_count,
        "sealed_segment_count": inspection.sealed_segment_count,
        "sealed_segment_ids": inspection.sealed_segment_ids,
        "result_count": inspection.result_count,
        "mutable_hit_count": inspection.mutable_hit_count,
        "sealed_hit_count": inspection.sealed_hit_count,
        "pre_filter_candidate_estimate": inspection.pre_filter_candidate_count,
        "post_filter_candidate_estimate": inspection.post_filter_candidate_count,
        "rerank_candidate_k": inspection.rerank_candidate_k,
        "search_latency_ms": inspection.search_latency_ms,
        "rerank_latency_ms": inspection.rerank_latency_ms,
        "total_latency_ms": inspection.total_latency_ms,
        "notes": build_collection_notes(collection_id=collection_id),
    }


def build_traced_trace_payload(*, db: Any, request: QueryRequest, hits: list[Any], base_mode: str, collection_id: str) -> dict[str, Any]:
    return {
        "mode": build_mode_name(base_mode, suffix="scored"),
        "top_k": request.top_k,
        "filters_applied": bool(request.filters),
        "mutable_live_count": len(db.mutable_buffer.live_entries()),
        "sealed_segment_count": len(db._segment_paths()),
        "result_count": len(hits),
        "rerank_candidate_k": max(request.top_k * 4, request.top_k) if request.approximate and request.rerank else None,
        "notes": build_collection_notes(collection_id=collection_id),
    }
