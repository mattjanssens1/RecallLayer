from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from recalllayer.api.recalllayer_sidecar_schemas import (
    SidecarCompactionRequest,
    SidecarDocumentUpsertRequest,
    SidecarFlushRequest,
    SidecarQueryRequest,
    SidecarRepairRequest,
    SidecarSearchResponse,
)
from recalllayer.sidecar import (
    InMemoryPostgresRepository,
    PsycopgPostgresRepository,
    RecallLayerSidecar,
)


@dataclass(slots=True)
class SidecarAppConfig:
    root_dir: str | Path = ".recalllayer_sidecar_http_db"
    collection_id: str = "recalllayer-sidecar-demo"
    host_repository: str = "inmemory"
    postgres_dsn: str | None = None
    postgres_table: str = "documents"
    api_key: str | None = None


AuthHeader = Annotated[str | None, Header(alias="x-api-key")] 


def load_sidecar_app_config_from_env() -> SidecarAppConfig:
    return SidecarAppConfig(
        root_dir=os.getenv("RECALLLAYER_SIDECAR_ROOT_DIR", ".recalllayer_sidecar_http_db"),
        collection_id=os.getenv("RECALLLAYER_COLLECTION_ID", "recalllayer-sidecar-demo"),
        host_repository=os.getenv("RECALLLAYER_HOST_REPOSITORY", "inmemory").strip().lower(),
        postgres_dsn=os.getenv("RECALLLAYER_POSTGRES_DSN"),
        postgres_table=os.getenv("RECALLLAYER_POSTGRES_TABLE", "documents"),
        api_key=os.getenv("RECALLLAYER_API_KEY"),
    )


def build_sidecar_from_config(config: SidecarAppConfig) -> RecallLayerSidecar:
    if config.host_repository == "inmemory":
        host_db = InMemoryPostgresRepository()
    elif config.host_repository == "postgres":
        if not config.postgres_dsn:
            raise RuntimeError(
                "RECALLLAYER_POSTGRES_DSN is required when RECALLLAYER_HOST_REPOSITORY=postgres"
            )
        host_db = PsycopgPostgresRepository.from_dsn(
            config.postgres_dsn,
            table_name=config.postgres_table,
        )
    else:
        raise RuntimeError(
            f"unsupported RECALLLAYER_HOST_REPOSITORY={config.host_repository!r}; "
            "expected 'inmemory' or 'postgres'"
        )
    return RecallLayerSidecar(
        host_db=host_db,
        root_dir=config.root_dir,
        collection_id=config.collection_id,
    )


def create_recalllayer_sidecar_app(
    *,
    root_dir: str | Path = ".recalllayer_sidecar_http_db",
    sidecar: RecallLayerSidecar | None = None,
    config: SidecarAppConfig | None = None,
) -> FastAPI:
    app_config = config or SidecarAppConfig(root_dir=root_dir)
    app = FastAPI(title="RecallLayer Sidecar")
    local_sidecar = sidecar or build_sidecar_from_config(app_config)
    app.state.sidecar = local_sidecar
    app.state.sidecar_config = app_config

    def require_api_key(x_api_key: AuthHeader = None) -> None:
        if app_config.api_key is None:
            return
        if x_api_key != app_config.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing or invalid x-api-key",
            )

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "collection_id": local_sidecar.collection_id,
            "host_repository": local_sidecar.host_db.__class__.__name__,
            "root_dir": str(local_sidecar.root_dir),
            "api_key_enabled": app_config.api_key is not None,
        }

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        return {
            "status": "ready",
            "collection_id": local_sidecar.collection_id,
            "host_repository": local_sidecar.host_db.__class__.__name__,
        }

    @app.get("/v1/status")
    def sidecar_status() -> dict[str, Any]:
        shard_ids = local_sidecar._known_shard_ids()
        return {
            "collection_id": local_sidecar.collection_id,
            "host_repository": local_sidecar.host_db.__class__.__name__,
            "root_dir": str(local_sidecar.root_dir),
            "api_key_enabled": app_config.api_key is not None,
            "known_shard_ids": shard_ids,
            "known_document_ids": local_sidecar.known_document_ids(),
        }

    @app.put("/v1/documents/{document_id}", dependencies=[Depends(require_api_key)])
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

    @app.post("/v1/documents/{document_id}/sync", dependencies=[Depends(require_api_key)])
    def sync_document(document_id: str) -> dict[str, Any]:
        vector_id = local_sidecar.sync_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id}

    @app.post("/v1/documents/{document_id}/unpublish", dependencies=[Depends(require_api_key)])
    def unpublish_document(document_id: str) -> dict[str, Any]:
        vector_id = local_sidecar.unpublish_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id, "status": "unpublished"}

    @app.delete("/v1/documents/{document_id}", dependencies=[Depends(require_api_key)])
    def delete_document(document_id: str) -> dict[str, Any]:
        vector_id = local_sidecar.delete_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id, "deleted": True}

    @app.post("/v1/query", response_model=SidecarSearchResponse, dependencies=[Depends(require_api_key)])
    def query(request: SidecarQueryRequest) -> SidecarSearchResponse:
        result = local_sidecar.search(
            request.query_text,
            top_k=request.top_k,
            region=request.region,
        )
        return SidecarSearchResponse(**result)

    @app.post("/v1/repair", dependencies=[Depends(require_api_key)])
    def repair(request: SidecarRepairRequest) -> dict[str, Any]:
        synced = local_sidecar.repair_documents(request.document_ids)
        return {
            "document_ids": request.document_ids or local_sidecar.known_document_ids(),
            "synced_vector_ids": synced,
        }

    @app.post("/v1/backfill", dependencies=[Depends(require_api_key)])
    def backfill() -> dict[str, Any]:
        synced = local_sidecar.backfill_from_host()
        return {"synced_vector_ids": synced}

    @app.post("/v1/flush", dependencies=[Depends(require_api_key)])
    def flush(request: SidecarFlushRequest) -> dict[str, Any]:
        local_sidecar.flush(segment_id=request.segment_id, generation=request.generation)
        shard_manifest, _segment_manifests = local_sidecar.recall_layer.load_manifest_set()
        return {
            "active_segment_ids": (
                shard_manifest.active_segment_ids if shard_manifest is not None else []
            ),
        }

    @app.post("/v1/compact", dependencies=[Depends(require_api_key)])
    def compact(request: SidecarCompactionRequest) -> dict[str, Any]:
        result = local_sidecar.compact(
            output_segment_id=request.output_segment_id,
            generation=request.generation,
            min_segment_count=request.min_segment_count,
            max_total_rows=request.max_total_rows,
        )
        return {"compacted": result is not None, "result": result}

    return app


app = create_recalllayer_sidecar_app(config=load_sidecar_app_config_from_env())
