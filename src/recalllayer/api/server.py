from __future__ import annotations

from fastapi import FastAPI, HTTPException

from recalllayer.api.schemas import QueryHit, QueryRequest, QueryResponse, UpsertRequest
from recalllayer.engine.mutable_buffer import MutableBuffer
from recalllayer.engine.query_executor import QueryExecutor
from recalllayer.quantization.scalar import ScalarQuantizer


def create_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database")

    mutable_buffer = MutableBuffer(collection_id="default")
    executor = QueryExecutor(mutable_buffer=mutable_buffer, quantizer=ScalarQuantizer())

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.put("/v1/vectors/{vector_id}")
    def upsert_vector(vector_id: str, request: UpsertRequest) -> dict[str, object]:
        write_epoch = mutable_buffer.watermark() + 1
        mutable_buffer.upsert(
            vector_id=vector_id,
            embedding=request.embedding,
            metadata=request.metadata,
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
            write_epoch=write_epoch,
        )
        return {"vector_id": vector_id, "write_epoch": write_epoch}

    @app.post("/v1/query", response_model=QueryResponse)
    def query(request: QueryRequest) -> QueryResponse:
        try:
            if request.approximate:
                results = executor.search_compressed(request.embedding, top_k=request.top_k)
                mode = "compressed"
            else:
                results = executor.search_exact(request.embedding, top_k=request.top_k)
                mode = "exact"
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return QueryResponse(
            results=[
                QueryHit(vector_id=result.vector_id, score=result.score, metadata=result.metadata)
                for result in results
            ],
            mode=mode,
        )

    return app


app = create_app()
