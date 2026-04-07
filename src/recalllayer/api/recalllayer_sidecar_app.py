from __future__ import annotations

import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status

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
    auto_flush_interval_seconds: int | None = None


AuthHeader = Annotated[str | None, Header(alias="x-api-key")] 


def load_sidecar_app_config_from_env() -> SidecarAppConfig:
    raw_interval = os.getenv("RECALLLAYER_AUTO_FLUSH_INTERVAL_SECONDS")
    auto_flush_interval: int | None = None
    if raw_interval is not None:
        try:
            auto_flush_interval = int(raw_interval)
            if auto_flush_interval <= 0:
                auto_flush_interval = None
        except ValueError:
            pass

    return SidecarAppConfig(
        root_dir=os.getenv("RECALLLAYER_SIDECAR_ROOT_DIR", ".recalllayer_sidecar_http_db"),
        collection_id=os.getenv("RECALLLAYER_COLLECTION_ID", "recalllayer-sidecar-demo"),
        host_repository=os.getenv("RECALLLAYER_HOST_REPOSITORY", "inmemory").strip().lower(),
        postgres_dsn=os.getenv("RECALLLAYER_POSTGRES_DSN"),
        postgres_table=os.getenv("RECALLLAYER_POSTGRES_TABLE", "documents"),
        api_key=os.getenv("RECALLLAYER_API_KEY"),
        auto_flush_interval_seconds=auto_flush_interval,
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


class _MetricsState:
    """Thread-safe counters for the Prometheus metrics endpoint."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.upserts_total: int = 0
        self.deletes_total: int = 0
        self.queries_total: int = 0
        self.flushes_total: int = 0
        self.auto_flushes_total: int = 0
        self.query_latency_seconds: list[float] = []

    def inc_upsert(self) -> None:
        with self._lock:
            self.upserts_total += 1

    def inc_delete(self) -> None:
        with self._lock:
            self.deletes_total += 1

    def inc_query(self, latency_seconds: float) -> None:
        with self._lock:
            self.queries_total += 1
            self.query_latency_seconds.append(latency_seconds)
            # Keep only the last 1 000 samples to bound memory.
            if len(self.query_latency_seconds) > 1000:
                self.query_latency_seconds = self.query_latency_seconds[-1000:]

    def inc_flush(self, *, auto: bool = False) -> None:
        with self._lock:
            self.flushes_total += 1
            if auto:
                self.auto_flushes_total += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = list(self.query_latency_seconds)
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        def pct(p: float) -> float:
            if not latencies_sorted:
                return 0.0
            idx = max(0, int(n * p) - 1)
            return latencies_sorted[min(idx, n - 1)]

        return {
            "upserts_total": self.upserts_total,
            "deletes_total": self.deletes_total,
            "queries_total": self.queries_total,
            "flushes_total": self.flushes_total,
            "auto_flushes_total": self.auto_flushes_total,
            "query_latency_p50_seconds": pct(0.50),
            "query_latency_p95_seconds": pct(0.95),
            "query_latency_p99_seconds": pct(0.99),
        }


def create_recalllayer_sidecar_app(
    *,
    root_dir: str | Path = ".recalllayer_sidecar_http_db",
    sidecar: RecallLayerSidecar | None = None,
    config: SidecarAppConfig | None = None,
) -> FastAPI:
    app_config = config or SidecarAppConfig(root_dir=root_dir)
    local_sidecar = sidecar or build_sidecar_from_config(app_config)
    metrics = _MetricsState()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task: asyncio.Task | None = None
        if app_config.auto_flush_interval_seconds is not None:
            task = asyncio.create_task(
                _auto_flush_loop(local_sidecar, app_config.auto_flush_interval_seconds, metrics)
            )
        yield
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="RecallLayer Sidecar", lifespan=lifespan)
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
        metrics.inc_upsert()
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
        metrics.inc_delete()
        return {"document_id": document_id, "vector_id": vector_id, "deleted": True}

    @app.post("/v1/query", response_model=SidecarSearchResponse, dependencies=[Depends(require_api_key)])
    def query(request: SidecarQueryRequest) -> SidecarSearchResponse:
        t0 = time.monotonic()
        result = local_sidecar.search(
            request.query_text,
            top_k=request.top_k,
            region=request.region,
        )
        metrics.inc_query(latency_seconds=time.monotonic() - t0)
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
        metrics.inc_flush()
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

    @app.get("/metrics")
    def prometheus_metrics() -> Response:
        """Return collection and request counters in Prometheus text format."""
        col_stats = local_sidecar.recall_layer.collection_stats()
        req_snap = metrics.snapshot()

        def g(name: str, help_text: str, value: float | int) -> list[str]:
            return [
                f"# HELP {name} {help_text}",
                f"# TYPE {name} gauge",
                f"{name} {value}",
            ]

        def c(name: str, help_text: str, value: float | int) -> list[str]:
            return [
                f"# HELP {name} {help_text}",
                f"# TYPE {name} counter",
                f"{name}_total {value}",
            ]

        lines: list[str] = []
        lines += g(
            "recalllayer_segment_count",
            "Number of active sealed segments.",
            col_stats["total_segment_count"],
        )
        lines += g(
            "recalllayer_mutable_buffer_size",
            "Number of un-flushed vectors in the mutable buffer.",
            col_stats["mutable_buffer_size"],
        )
        lines += g(
            "recalllayer_delete_ratio",
            "Fraction of sealed rows that are tombstoned (0..1).",
            col_stats["total_delete_ratio"],
        )
        lines += g(
            "recalllayer_storage_bytes",
            "Total bytes used by sealed segment files on disk.",
            col_stats["storage_bytes"],
        )
        lines += g(
            "recalllayer_shard_count",
            "Number of shards known to the collection.",
            col_stats["shard_count"],
        )
        lines += c(
            "recalllayer_upserts",
            "Total document upsert calls since startup.",
            req_snap["upserts_total"],
        )
        lines += c(
            "recalllayer_deletes",
            "Total document delete calls since startup.",
            req_snap["deletes_total"],
        )
        lines += c(
            "recalllayer_queries",
            "Total query calls since startup.",
            req_snap["queries_total"],
        )
        lines += c(
            "recalllayer_flushes",
            "Total flush calls since startup (manual + auto).",
            req_snap["flushes_total"],
        )
        lines += c(
            "recalllayer_auto_flushes",
            "Total automatic background flush calls since startup.",
            req_snap["auto_flushes_total"],
        )
        lines += g(
            "recalllayer_query_latency_p50_seconds",
            "p50 query latency over last 1000 requests.",
            req_snap["query_latency_p50_seconds"],
        )
        lines += g(
            "recalllayer_query_latency_p95_seconds",
            "p95 query latency over last 1000 requests.",
            req_snap["query_latency_p95_seconds"],
        )
        lines += g(
            "recalllayer_query_latency_p99_seconds",
            "p99 query latency over last 1000 requests.",
            req_snap["query_latency_p99_seconds"],
        )
        lines.append("")
        return Response(content="\n".join(lines), media_type="text/plain; version=0.0.4")

    return app


async def _auto_flush_loop(
    sidecar: RecallLayerSidecar,
    interval_seconds: int,
    metrics: _MetricsState,
) -> None:
    """Background asyncio task: flush the mutable buffer on a fixed interval."""
    flush_counter = 0
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            buf_size = len(sidecar.recall_layer.mutable_buffer.all_entries())
            if buf_size > 0:
                flush_counter += 1
                segment_id = f"seg-auto-{int(time.time())}-{flush_counter}"
                sidecar.flush(segment_id=segment_id, generation=flush_counter)
                metrics.inc_flush(auto=True)
        except Exception:
            # Never crash the background task; errors surface via /metrics staleness.
            pass


app = create_recalllayer_sidecar_app(config=load_sidecar_app_config_from_env())
