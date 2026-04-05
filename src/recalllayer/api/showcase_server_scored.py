from __future__ import annotations

from fastapi import FastAPI

from recalllayer.api.schemas import QueryRequest, QueryResponse, UpsertRequest
from recalllayer.api.showcase_query_api import QuerySurfaceRunner, build_scored_query_response
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


def create_scored_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Scored")
    db = ShowcaseScoredDatabase(collection_id="showcase-scored", root_dir=".showcase_scored_api_db")
    runner = QuerySurfaceRunner(db=db)

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
        hits, base_mode, _rerank_candidate_k = runner.execute_hits(request)
        return build_scored_query_response(hits=hits, base_mode=base_mode)

    return app


app = create_scored_showcase_app()
