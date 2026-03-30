from __future__ import annotations

from fastapi import FastAPI

from turboquant_db.api.schemas import QueryHit, QueryRequest, UpsertRequest
from turboquant_db.api.trace_schemas import QueryTrace, TraceableQueryResponse
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase


def create_traced_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Traced")
    db = ShowcaseScoredDatabase(collection_id="showcase-traced", root_dir=".showcase_traced_api_db")

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

    @app.post("/v1/query", response_model=TraceableQueryResponse)
    def query(request: QueryRequest) -> TraceableQueryResponse:
        if request.approximate and request.rerank:
            hits = db.query_compressed_reranked_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-reranked-hybrid-scored"
            rerank_candidate_k = max(request.top_k * 4, request.top_k)
        elif request.approximate:
            hits = db.query_compressed_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-hybrid-scored"
            rerank_candidate_k = None
        else:
            hits = db.query_exact_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "exact-hybrid-scored"
            rerank_candidate_k = None

        trace = QueryTrace(
            mode=mode,
            top_k=request.top_k,
            filters_applied=bool(request.filters),
            mutable_live_count=len(db.mutable_buffer.live_entries()),
            sealed_segment_count=len(db._segment_paths()),
            result_count=len(hits),
            rerank_candidate_k=rerank_candidate_k,
            notes={"collection_id": db.collection_id},
        )

        return TraceableQueryResponse(
            results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in hits],
            mode=mode,
            trace=trace,
        )

    return app


app = create_traced_showcase_app()
