from __future__ import annotations

from fastapi import FastAPI

from turboquant_db.api.schemas import QueryHit, QueryRequest, QueryResponse, UpsertRequest
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase


def create_scored_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Scored")
    db = ShowcaseScoredDatabase(collection_id="showcase-scored", root_dir=".showcase_scored_api_db")

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

    @app.post("/v1/query", response_model=QueryResponse)
    def query(request: QueryRequest) -> QueryResponse:
        if request.approximate and request.rerank:
            hits = db.query_compressed_reranked_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-reranked-hybrid-scored"
        elif request.approximate:
            hits = db.query_compressed_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-hybrid-scored"
        else:
            hits = db.query_exact_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "exact-hybrid-scored"

        return QueryResponse(
            results=[
                QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata)
                for hit in hits
            ],
            mode=mode,
        )

    return app


app = create_scored_showcase_app()
