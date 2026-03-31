from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI

from turboquant_db.api.observed_plus_schemas import ObservedPlusQueryResponse, ObservedPlusQueryTrace
from turboquant_db.api.schemas import QueryHit, QueryRequest, UpsertRequest
from turboquant_db.api.showcase_notes import build_collection_notes
from turboquant_db.api.showcase_query_api import QuerySurfaceRunner, build_mode_name, count_hit_sources, segment_ids_for_paths
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase


def create_observed_plus_showcase_app() -> FastAPI:
    app = FastAPI(title="TurboQuant Native Vector Database Showcase Observed Plus")
    db = ShowcaseScoredDatabase(collection_id="showcase-observed-plus", root_dir=".showcase_observed_plus_api_db")
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

    @app.post("/v1/query", response_model=ObservedPlusQueryResponse)
    def query(request: QueryRequest) -> ObservedPlusQueryResponse:
        segment_paths = db._segment_paths()
        start = perf_counter()
        hits, base_mode, rerank_candidate_k = runner.execute_hits(request)
        latency_ms = (perf_counter() - start) * 1000.0

        mutable_hit_count, sealed_hit_count = count_hit_sources(db=db, hits=hits)

        candidate_estimate = max(len(hits), rerank_candidate_k or len(hits))
        trace = ObservedPlusQueryTrace(
            mode=build_mode_name(base_mode, suffix="observed-plus"),
            top_k=request.top_k,
            filters_applied=bool(request.filters),
            mutable_live_count=len(db.mutable_buffer.live_entries()),
            sealed_segment_count=len(segment_paths),
            sealed_segment_ids=segment_ids_for_paths(segment_paths),
            result_count=len(hits),
            mutable_hit_count=mutable_hit_count,
            sealed_hit_count=sealed_hit_count,
            rerank_candidate_k=rerank_candidate_k,
            latency_ms=latency_ms,
            candidate_count_estimate=candidate_estimate,
            pre_filter_candidate_estimate=candidate_estimate,
            post_filter_candidate_estimate=len(hits),
            notes=build_collection_notes(collection_id=db.collection_id),
        )

        return ObservedPlusQueryResponse(
            results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in hits],
            mode=build_mode_name(base_mode, suffix="observed-plus"),
            trace=trace,
        )

    return app


app = create_observed_plus_showcase_app()
