from __future__ import annotations

from fastapi import FastAPI

from turboquant_db.api.measured_schemas import MeasuredQueryResponse, MeasuredQueryTrace, MeasuredTimingBreakdown
from turboquant_db.api.schemas import QueryHit, QueryRequest, UpsertRequest
from turboquant_db.engine.inspected_db import InspectedShowcaseDatabase
from turboquant_db.engine.query_trace_export import build_query_trace_payload


def create_measured_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Measured")
    db = InspectedShowcaseDatabase(collection_id="showcase-measured", root_dir=".showcase_measured_api_db")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.put("/v1/vectors/{vector_id}")
    def upsert_vector(vector_id: str, request: UpsertRequest) -> dict[str, object]:
        write_epoch = db.upsert(vector_id=vector_id, embedding=request.embedding, metadata=request.metadata)
        return {"vector_id": vector_id, "write_epoch": write_epoch}

    @app.post("/v1/flush")
    def flush() -> dict[str, object]:
        manifest = db.flush_mutable(segment_id=f"seg-{db.mutable_buffer.watermark()}", generation=1)
        return {"active_segment_ids": manifest.active_segment_ids}

    @app.post("/v1/query", response_model=MeasuredQueryResponse)
    def query(request: QueryRequest) -> MeasuredQueryResponse:
        if request.approximate and request.rerank:
            result = db.query_compressed_reranked_hybrid_inspected(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
        elif request.approximate:
            result = db.query_compressed_hybrid_inspected(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
        else:
            result = db.query_exact_hybrid_inspected(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )

        inspection = result.inspection
        exported_trace = build_query_trace_payload(
            inspection=inspection,
            plan=result.plan,
            stats=result.stats,
            notes={"collection_id": db.collection_id},
        )
        trace = MeasuredQueryTrace(
            mode=inspection.mode,
            top_k=inspection.top_k,
            filters_applied=inspection.filters_applied,
            mutable_live_count=inspection.mutable_live_count,
            sealed_segment_count=inspection.sealed_segment_count,
            sealed_segment_ids=inspection.sealed_segment_ids,
            result_count=inspection.result_count,
            mutable_hit_count=inspection.mutable_hit_count,
            sealed_hit_count=inspection.sealed_hit_count,
            pre_filter_candidate_count=inspection.pre_filter_candidate_count,
            post_filter_candidate_count=inspection.post_filter_candidate_count,
            rerank_candidate_k=inspection.rerank_candidate_k,
            search_latency_ms=inspection.search_latency_ms,
            rerank_latency_ms=inspection.rerank_latency_ms,
            total_latency_ms=inspection.total_latency_ms,
            timing_breakdown=MeasuredTimingBreakdown(**exported_trace["inspection"]["timing_breakdown"]),
            notes={"collection_id": db.collection_id},
            exported_trace=exported_trace,
        )
        return MeasuredQueryResponse(
            results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in result.hits],
            mode=inspection.mode,
            trace=trace,
        )

    return app


app = create_measured_showcase_app()
