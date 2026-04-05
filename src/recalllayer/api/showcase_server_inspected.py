from __future__ import annotations

from fastapi import FastAPI

from recalllayer.api.inspected_schemas import InspectedQueryResponse, InspectedQueryTrace
from recalllayer.api.schemas import QueryHit, QueryRequest, UpsertRequest
from recalllayer.api.showcase_trace_api import InspectedSurfaceRunner, build_inspected_trace_payload
from recalllayer.engine.inspected_db import InspectedShowcaseDatabase


def create_inspected_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Inspected")
    db = InspectedShowcaseDatabase(collection_id="showcase-inspected", root_dir=".showcase_inspected_api_db")
    runner = InspectedSurfaceRunner(db=db)

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
        result = runner.execute(request)
        trace = InspectedQueryTrace(**build_inspected_trace_payload(request=request, result=result, collection_id=db.collection_id))

        return InspectedQueryResponse(
            results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in result.hits],
            mode=result.inspection.mode,
            trace=trace,
        )

    return app


app = create_inspected_showcase_app()
