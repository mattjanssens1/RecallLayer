from __future__ import annotations

from fastapi import FastAPI

from turboquant_db.api.schemas import QueryHit, QueryRequest, UpsertRequest
from turboquant_db.api.showcase_query_api import QuerySurfaceRunner, build_mode_name
from turboquant_db.api.showcase_trace_api import build_traced_trace_payload
from turboquant_db.api.trace_schemas import QueryTrace, TraceableQueryResponse
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase


def create_traced_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Traced")
    db = ShowcaseScoredDatabase(collection_id="showcase-traced", root_dir=".showcase_traced_api_db")
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

    @app.post("/v1/query", response_model=TraceableQueryResponse)
    def query(request: QueryRequest) -> TraceableQueryResponse:
        hits, base_mode, rerank_candidate_k = runner.execute_hits(request)

        trace = QueryTrace(**build_traced_trace_payload(db=db, request=request, hits=hits, base_mode=base_mode, collection_id=db.collection_id))

        return TraceableQueryResponse(
            results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in hits],
            mode=build_mode_name(base_mode, suffix="scored"),
            trace=trace,
        )

    return app


app = create_traced_showcase_app()
