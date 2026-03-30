from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI

from turboquant_db.api.observed_schemas import ObservedQueryResponse, ObservedQueryTrace
from turboquant_db.api.schemas import QueryHit, QueryRequest, UpsertRequest
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase


def create_observed_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Observed")
    db = ShowcaseScoredDatabase(collection_id="showcase-observed", root_dir=".showcase_observed_api_db")

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

    @app.post("/v1/query", response_model=ObservedQueryResponse)
    def query(request: QueryRequest) -> ObservedQueryResponse:
        segment_paths = db._segment_paths()
        start = perf_counter()
        if request.approximate and request.rerank:
            hits = db.query_compressed_reranked_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-reranked-hybrid-observed"
            rerank_candidate_k = max(request.top_k * 4, request.top_k)
        elif request.approximate:
            hits = db.query_compressed_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-hybrid-observed"
            rerank_candidate_k = None
        else:
            hits = db.query_exact_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "exact-hybrid-observed"
            rerank_candidate_k = None
        latency_ms = (perf_counter() - start) * 1000.0

        trace = ObservedQueryTrace(
            mode=mode,
            top_k=request.top_k,
            filters_applied=bool(request.filters),
            mutable_live_count=len(db.mutable_buffer.live_entries()),
            sealed_segment_count=len(segment_paths),
            sealed_segment_ids=[path.split("/")[-1] for path in segment_paths],
            result_count=len(hits),
            rerank_candidate_k=rerank_candidate_k,
            latency_ms=latency_ms,
            candidate_count_estimate=max(len(hits), rerank_candidate_k or len(hits)),
            notes={"collection_id": db.collection_id},
        )

        return ObservedQueryResponse(
            results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in hits],
            mode=mode,
            trace=trace,
        )

    return app


app = create_observed_showcase_app()
