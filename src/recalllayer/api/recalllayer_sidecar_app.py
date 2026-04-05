from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI

from recalllayer.api.recalllayer_sidecar_schemas import (
    SidecarCompactionRequest,
    SidecarDocumentUpsertRequest,
    SidecarFlushRequest,
    SidecarQueryRequest,
    SidecarRepairRequest,
    SidecarSearchResponse,
)
from recalllayer.sidecar import InMemoryPostgresRepository, RecallLayerSidecar


def create_recalllayer_sidecar_app(
    *,
    root_dir: str | Path = ".recalllayer_sidecar_http_db",
    sidecar: RecallLayerSidecar | None = None,
) -> FastAPI:
    app = FastAPI(title="RecallLayer Sidecar")
    local_sidecar = sidecar or RecallLayerSidecar(
        host_db=InMemoryPostgresRepository(),
        root_dir=root_dir,
    )
    app.state.sidecar = local_sidecar

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "collection_id": local_sidecar.collection_id,
            "host_repository": local_sidecar.host_db.__class__.__name__,
        }

    @app.put("/v1/documents/{document_id}")
    def upsert_document(document_id: str, request: SidecarDocumentUpsertRequest) -> dict[str, Any]:
        vector_id = local_sidecar.upsert_and_sync_document(
            document_id=document_id,
            title=request.title,
            body=request.body,
            region=request.region,
            status=request.status,
        )
        return {
            "document_id": document_id,
            "vector_id": vector_id,
            "status": request.status,
        }

    @app.post("/v1/documents/{document_id}/sync")
    def sync_document(document_id: str) -> dict[str, Any]:
        vector_id = local_sidecar.sync_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id}

    @app.post("/v1/documents/{document_id}/unpublish")
    def unpublish_document(document_id: str) -> dict[str, Any]:
        vector_id = local_sidecar.unpublish_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id, "status": "unpublished"}

    @app.delete("/v1/documents/{document_id}")
    def delete_document(document_id: str) -> dict[str, Any]:
        vector_id = local_sidecar.delete_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id, "deleted": True}

    @app.post("/v1/query", response_model=SidecarSearchResponse)
    def query(request: SidecarQueryRequest) -> SidecarSearchResponse:
        result = local_sidecar.search(
            request.query_text,
            top_k=request.top_k,
            region=request.region,
        )
        return SidecarSearchResponse(**result)

    @app.post("/v1/repair")
    def repair(request: SidecarRepairRequest) -> dict[str, Any]:
        synced = local_sidecar.repair_documents(request.document_ids)
        return {
            "document_ids": request.document_ids or local_sidecar.known_document_ids(),
            "synced_vector_ids": synced,
        }

    @app.post("/v1/backfill")
    def backfill() -> dict[str, Any]:
        synced = local_sidecar.backfill_from_host()
        return {"synced_vector_ids": synced}

    @app.post("/v1/flush")
    def flush(request: SidecarFlushRequest) -> dict[str, Any]:
        local_sidecar.flush(segment_id=request.segment_id, generation=request.generation)
        shard_manifest, _segment_manifests = local_sidecar.recall_layer.load_manifest_set()
        return {
            "active_segment_ids": (
                shard_manifest.active_segment_ids if shard_manifest is not None else []
            ),
        }

    @app.post("/v1/compact")
    def compact(request: SidecarCompactionRequest) -> dict[str, Any]:
        result = local_sidecar.compact(
            output_segment_id=request.output_segment_id,
            generation=request.generation,
            min_segment_count=request.min_segment_count,
            max_total_rows=request.max_total_rows,
        )
        return {"compacted": result is not None, "result": result}

    return app


app = create_recalllayer_sidecar_app()
