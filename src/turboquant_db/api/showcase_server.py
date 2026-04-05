from __future__ import annotations

from fastapi import FastAPI

from turboquant_db.api.schemas import QueryHit, QueryRequest, QueryResponse, UpsertRequest
from turboquant_db.engine.showcase_rerank_db import ShowcaseRerankDatabase


def create_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase")
    db = ShowcaseRerankDatabase(collection_id="showcase", root_dir=".showcase_api_db")

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
            vector_ids = db.query_compressed_reranked_hybrid(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-reranked-hybrid"
        elif request.approximate:
            vector_ids = db.query_compressed_hybrid(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "compressed-hybrid"
        else:
            vector_ids = db.query_exact_hybrid(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            )
            mode = "exact-hybrid"

        return QueryResponse(
            results=[QueryHit(vector_id=vector_id, score=0.0, metadata={}) for vector_id in vector_ids],
            mode=mode,
        )

    return app


app = create_showcase_app()
