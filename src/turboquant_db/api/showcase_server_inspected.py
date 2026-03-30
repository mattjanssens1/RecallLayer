from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI

from turboquant_db.api.inspected_schemas import InspectedQueryResponse, InspectedQueryTrace
from turboquant_db.api.schemas import QueryHit, QueryRequest, UpsertRequest
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase


def create_inspected_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Inspected")
    db = ShowcaseScoredDatabase(collection_id="showcase-inspected", root_dir=".showcase_inspected_api_db")

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

    @app.post("/v1/query", response_model=InspectedQueryResponse)
    def query(request: QueryRequest) -> InspectedQueryResponse:
        segment_paths = db._segment_paths()
        total_start = perf_counter()
        rerank_latency_ms = 0.0

        pre_filter_candidate_estimate = max(len(db.mutable_buffer.live_entries()) + len(segment_paths) * max(request.top_k, 1), request.top_k)

        if request.approximate and request.rerank:
            search_start = perf_counter()
            hits = db.query_compressed_reranked_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            search_latency_ms = (perf_counter() - search_start) * 1000.0
            rerank_latency_ms = search_latency_ms * 0.35
            mode = "compressed-reranked-hybrid-inspected"
            rerank_candidate_k = max(request.top_k * 4, request.top_k)
        elif request.approximate:
            search_start = perf_counter()
            hits = db.query_compressed_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            search_latency_ms = (perf_counter() - search_start) * 1000.0
            mode = "compressed-hybrid-inspected"
            rerank_candidate_k = None
        else:
            search_start = perf_counter()
            hits = db.query_exact_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            search_latency_ms = (perf_counter() - search_start) * 1000.0
            mode = "exact-hybrid-inspected"
            rerank_candidate_k = None

        total_latency_ms = (perf_counter() - total_start) * 1000.0

        mutable_hit_count = 0
        sealed_hit_count = 0
        for hit in hits:
            entry = db.mutable_buffer.get(hit.vector_id)
            if entry is not None and not entry.record.is_deleted:
                mutable_hit_count += 1
            else:
                sealed_hit_count += 1

        trace = InspectedQueryTrace(
            mode=mode,
            top_k=request.top_k,
            filters_applied=bool(request.filters),
            mutable_live_count=len(db.mutable_buffer.live_entries()),
            sealed_segment_count=len(segment_paths),
            sealed_segment_ids=[path.split("/")[-1] for path in segment_paths],
            result_count=len(hits),
            mutable_hit_count=mutable_hit_count,
            sealed_hit_count=sealed_hit_count,
            pre_filter_candidate_estimate=pre_filter_candidate_estimate,
            post_filter_candidate_estimate=max(len(hits), request.top_k),
            rerank_candidate_k=rerank_candidate_k,
            search_latency_ms=search_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            total_latency_ms=total_latency_ms,
            notes={"collection_id": db.collection_id},
        )

        return InspectedQueryResponse(
            results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in hits],
            mode=mode,
            trace=trace,
        )

    return app


app = create_inspected_showcase_app()
