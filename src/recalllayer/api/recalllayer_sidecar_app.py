from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status

from recalllayer.api.rate_limiter import SlidingWindowRateLimiter
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TenantConfig:
    """Maps an API key to an isolated collection namespace."""

    api_key: str
    collection_id: str


@dataclass
class SidecarAppConfig:
    root_dir: str | Path = ".recalllayer_sidecar_http_db"
    collection_id: str = "recalllayer-sidecar-demo"
    host_repository: str = "inmemory"
    postgres_dsn: str | None = None
    postgres_table: str = "documents"
    # Single-tenant auth (legacy)
    api_key: str | None = None
    # Multi-tenant: list of TenantConfig entries derived from RECALLLAYER_TENANTS
    tenants: list[TenantConfig] = field(default_factory=list)
    # Rate limiting
    rate_limit: int = 0  # 0 = disabled; N = max requests per minute per key
    # Auto-flush scheduler (0 or None = disabled)
    auto_flush_interval_sec: float = 0.0
    auto_flush_upsert_threshold: int = 10_000
    # Dynamic IVF: auto-enable when live row count crosses this threshold (None = disabled)
    ivf_auto_threshold: int | None = 50_000


AuthHeader = Annotated[str | None, Header(alias="x-api-key")]


def _parse_tenants(raw: str) -> list[TenantConfig]:
    """Parse ``key1:ns1,key2:ns2`` into a list of TenantConfig objects."""
    tenants: list[TenantConfig] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise ValueError(
                f"RECALLLAYER_TENANTS entry {pair!r} must be in 'api_key:collection_id' format"
            )
        api_key, _, collection_id = pair.partition(":")
        api_key = api_key.strip()
        collection_id = collection_id.strip()
        if not api_key or not collection_id:
            raise ValueError(
                f"RECALLLAYER_TENANTS entry {pair!r}: api_key and collection_id must be non-empty"
            )
        tenants.append(TenantConfig(api_key=api_key, collection_id=collection_id))
    return tenants


def load_sidecar_app_config_from_env() -> SidecarAppConfig:
    tenants: list[TenantConfig] = []
    raw_tenants = os.getenv("RECALLLAYER_TENANTS", "").strip()
    if raw_tenants:
        tenants = _parse_tenants(raw_tenants)

    # Support both RECALLLAYER_AUTO_FLUSH_INTERVAL_SEC and the long form
    # RECALLLAYER_AUTO_FLUSH_INTERVAL_SECONDS (documented in DEPLOYMENT.md).
    raw_interval = (
        os.getenv("RECALLLAYER_AUTO_FLUSH_INTERVAL_SEC")
        or os.getenv("RECALLLAYER_AUTO_FLUSH_INTERVAL_SECONDS")
    )
    auto_flush_interval_sec: float = 0.0
    if raw_interval:
        try:
            v = float(raw_interval)
            if v > 0:
                auto_flush_interval_sec = v
        except ValueError:
            pass

    return SidecarAppConfig(
        root_dir=os.getenv("RECALLLAYER_SIDECAR_ROOT_DIR", ".recalllayer_sidecar_http_db"),
        collection_id=os.getenv("RECALLLAYER_COLLECTION_ID", "recalllayer-sidecar-demo"),
        host_repository=os.getenv("RECALLLAYER_HOST_REPOSITORY", "inmemory").strip().lower(),
        postgres_dsn=os.getenv("RECALLLAYER_POSTGRES_DSN"),
        postgres_table=os.getenv("RECALLLAYER_POSTGRES_TABLE", "documents"),
        api_key=os.getenv("RECALLLAYER_API_KEY") or None,
        tenants=tenants,
        rate_limit=int(os.getenv("RECALLLAYER_RATE_LIMIT", "0")),
        auto_flush_interval_sec=auto_flush_interval_sec,
        auto_flush_upsert_threshold=int(
            os.getenv("RECALLLAYER_AUTO_FLUSH_UPSERT_THRESHOLD", "10000")
        ),
        ivf_auto_threshold=(
            int(os.getenv("RECALLLAYER_IVF_AUTO_THRESHOLD"))
            if os.getenv("RECALLLAYER_IVF_AUTO_THRESHOLD")
            else 50_000
        ),
    )


# ---------------------------------------------------------------------------
# Sidecar factory helpers
# ---------------------------------------------------------------------------


def _build_host_db(config: SidecarAppConfig):
    if config.host_repository == "inmemory":
        return InMemoryPostgresRepository()
    if config.host_repository == "postgres":
        if not config.postgres_dsn:
            raise RuntimeError(
                "RECALLLAYER_POSTGRES_DSN is required when RECALLLAYER_HOST_REPOSITORY=postgres"
            )
        return PsycopgPostgresRepository.from_dsn(
            config.postgres_dsn,
            table_name=config.postgres_table,
        )
    raise RuntimeError(
        f"unsupported RECALLLAYER_HOST_REPOSITORY={config.host_repository!r}; "
        "expected 'inmemory' or 'postgres'"
    )


def build_sidecar_from_config(
    config: SidecarAppConfig, *, collection_id: str | None = None
) -> RecallLayerSidecar:
    return RecallLayerSidecar(
        host_db=_build_host_db(config),
        root_dir=config.root_dir,
        collection_id=collection_id or config.collection_id,
        ivf_auto_threshold=config.ivf_auto_threshold,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Auto-flush background scheduler
# ---------------------------------------------------------------------------


class AutoFlushScheduler:
    """Background thread that periodically flushes sidecar buffers.

    Flushes when either:
    - *interval_sec* seconds have elapsed since the last flush, OR
    - the mutable buffer has grown beyond *upsert_threshold* entries.

    The scheduler runs in a daemon thread so it does not prevent process exit.
    """

    def __init__(
        self,
        *,
        sidecars: dict[str, RecallLayerSidecar],
        interval_sec: float,
        upsert_threshold: int,
        metrics: _MetricsState | None = None,
        poll_sec: float = 1.0,
    ) -> None:
        self._sidecars = sidecars
        self._interval_sec = interval_sec
        self._upsert_threshold = upsert_threshold
        self._metrics = metrics
        self._poll_sec = poll_sec
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="recalllayer-autoflush")
        self._flush_counter: dict[str, int] = {}

    def start(self) -> None:
        self._thread.start()
        logger.info(
            "AutoFlushScheduler started (interval=%.0fs, threshold=%d upserts)",
            self._interval_sec,
            self._upsert_threshold,
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        last_flush_at = time.monotonic()
        while not self._stop.wait(timeout=self._poll_sec):
            now = time.monotonic()
            elapsed = now - last_flush_at
            for collection_id, sidecar in list(self._sidecars.items()):
                try:
                    buf_size = sum(
                        len(buf.all_entries())
                        for buf in sidecar.recall_layer._shard_buffers.values()
                    )
                    should_flush = (
                        elapsed >= self._interval_sec
                        or buf_size >= self._upsert_threshold
                    )
                    if should_flush and buf_size > 0:
                        counter = self._flush_counter.get(collection_id, 0) + 1
                        self._flush_counter[collection_id] = counter
                        sidecar.flush(
                            segment_id=f"seg-auto-{counter}",
                            generation=counter,
                        )
                        if self._metrics is not None:
                            self._metrics.inc_flush(auto=True)
                        logger.info(
                            "AutoFlush: flushed collection=%s segment=seg-auto-%d buf_size=%d",
                            collection_id,
                            counter,
                            buf_size,
                        )
                except Exception:
                    logger.exception(
                        "AutoFlush: error flushing collection=%s", collection_id
                    )
            if elapsed >= self._interval_sec:
                last_flush_at = now


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_recalllayer_sidecar_app(
    *,
    root_dir: str | Path = ".recalllayer_sidecar_http_db",
    sidecar: RecallLayerSidecar | None = None,
    config: SidecarAppConfig | None = None,
) -> FastAPI:
    app_config = config or SidecarAppConfig(root_dir=root_dir)
    metrics = _MetricsState()

    # ------------------------------------------------------------------
    # Multi-tenancy: build a sidecar per tenant; fall back to single sidecar
    # ------------------------------------------------------------------
    tenant_sidecars: dict[str, RecallLayerSidecar] = {}  # api_key -> sidecar
    collection_sidecars: dict[str, RecallLayerSidecar] = {}  # collection_id -> sidecar

    if app_config.tenants:
        for tenant in app_config.tenants:
            sc = build_sidecar_from_config(app_config, collection_id=tenant.collection_id)
            tenant_sidecars[tenant.api_key] = sc
            collection_sidecars[tenant.collection_id] = sc
        default_sidecar = next(iter(tenant_sidecars.values()))
    else:
        default_sidecar = sidecar or build_sidecar_from_config(app_config)
        if app_config.api_key:
            tenant_sidecars[app_config.api_key] = default_sidecar
        collection_sidecars[app_config.collection_id] = default_sidecar

    # ------------------------------------------------------------------
    # Rate limiter
    # ------------------------------------------------------------------
    rate_limiter: SlidingWindowRateLimiter | None = None
    if app_config.rate_limit > 0:
        rate_limiter = SlidingWindowRateLimiter(
            max_requests=app_config.rate_limit, window_seconds=60.0
        )
        logger.info("Rate limiting enabled: %d req/min per key", app_config.rate_limit)

    # ------------------------------------------------------------------
    # Auto-flush scheduler
    # ------------------------------------------------------------------
    scheduler: AutoFlushScheduler | None = None
    if app_config.auto_flush_interval_sec > 0:
        scheduler = AutoFlushScheduler(
            sidecars=collection_sidecars,
            interval_sec=app_config.auto_flush_interval_sec,
            upsert_threshold=app_config.auto_flush_upsert_threshold,
            metrics=metrics,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if scheduler is not None:
            scheduler.start()
        yield
        if scheduler is not None:
            scheduler.stop()

    app = FastAPI(title="RecallLayer Sidecar", lifespan=lifespan)
    app.state.sidecar = default_sidecar
    app.state.sidecar_config = app_config
    app.state.tenant_sidecars = tenant_sidecars

    # ------------------------------------------------------------------
    # Auth + rate-limit dependency
    # ------------------------------------------------------------------

    def _resolve_sidecar(x_api_key: str | None) -> RecallLayerSidecar:
        """Validate API key and return the sidecar for the caller's tenant."""
        if app_config.tenants:
            if x_api_key is None or x_api_key not in tenant_sidecars:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="missing or invalid x-api-key",
                )
            return tenant_sidecars[x_api_key]

        if app_config.api_key is not None and x_api_key != app_config.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing or invalid x-api-key",
            )
        return default_sidecar

    def require_auth(request: Request, x_api_key: AuthHeader = None) -> RecallLayerSidecar:
        sc = _resolve_sidecar(x_api_key)
        if rate_limiter is not None:
            identifier = x_api_key or (request.client.host if request.client else "anonymous")
            allowed, retry_after = rate_limiter.check(identifier)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="rate limit exceeded",
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )
        return sc

    def require_api_key_no_tenant(x_api_key: AuthHeader = None) -> None:
        if app_config.api_key is None and not app_config.tenants:
            return
        if app_config.tenants and (x_api_key is None or x_api_key not in tenant_sidecars):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing or invalid x-api-key",
            )
        if app_config.api_key is not None and x_api_key != app_config.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing or invalid x-api-key",
            )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "collection_id": default_sidecar.collection_id,
            "host_repository": default_sidecar.host_db.__class__.__name__,
            "root_dir": str(default_sidecar.root_dir),
            "api_key_enabled": app_config.api_key is not None or bool(app_config.tenants),
            "multi_tenant": bool(app_config.tenants),
            "tenant_count": len(app_config.tenants),
            "rate_limit_rpm": app_config.rate_limit if app_config.rate_limit > 0 else None,
            "auto_flush_interval_sec": (
                app_config.auto_flush_interval_sec
                if app_config.auto_flush_interval_sec > 0
                else None
            ),
        }

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        return {
            "status": "ready",
            "collection_id": default_sidecar.collection_id,
            "host_repository": default_sidecar.host_db.__class__.__name__,
        }

    @app.get("/v1/status", dependencies=[Depends(require_api_key_no_tenant)])
    def sidecar_status() -> dict[str, Any]:
        shard_ids = default_sidecar._known_shard_ids()
        return {
            "collection_id": default_sidecar.collection_id,
            "host_repository": default_sidecar.host_db.__class__.__name__,
            "root_dir": str(default_sidecar.root_dir),
            "api_key_enabled": app_config.api_key is not None or bool(app_config.tenants),
            "known_shard_ids": shard_ids,
            "known_document_ids": default_sidecar.known_document_ids(),
        }

    @app.put("/v1/documents/{document_id}")
    def upsert_document(
        document_id: str,
        request: SidecarDocumentUpsertRequest,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> dict[str, Any]:
        vector_id = sc.upsert_and_sync_document(
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

    @app.post("/v1/documents/{document_id}/sync")
    def sync_document(
        document_id: str,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> dict[str, Any]:
        vector_id = sc.sync_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id}

    @app.post("/v1/documents/{document_id}/unpublish")
    def unpublish_document(
        document_id: str,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> dict[str, Any]:
        vector_id = sc.unpublish_document(document_id)
        return {"document_id": document_id, "vector_id": vector_id, "status": "unpublished"}

    @app.delete("/v1/documents/{document_id}")
    def delete_document(
        document_id: str,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> dict[str, Any]:
        vector_id = sc.delete_document(document_id)
        metrics.inc_delete()
        return {"document_id": document_id, "vector_id": vector_id, "deleted": True}

    @app.post("/v1/query", response_model=SidecarSearchResponse)
    def query(
        request: SidecarQueryRequest,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> SidecarSearchResponse:
        t0 = time.monotonic()
        result = sc.search(
            request.query_text,
            top_k=request.top_k,
            region=request.region,
        )
        metrics.inc_query(latency_seconds=time.monotonic() - t0)
        return SidecarSearchResponse(**result)

    @app.post("/v1/repair")
    def repair(
        request: SidecarRepairRequest,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> dict[str, Any]:
        synced = sc.repair_documents(request.document_ids)
        return {
            "document_ids": request.document_ids or sc.known_document_ids(),
            "synced_vector_ids": synced,
        }

    @app.post("/v1/backfill")
    def backfill(sc: RecallLayerSidecar = Depends(require_auth)) -> dict[str, Any]:
        synced = sc.backfill_from_host()
        return {"synced_vector_ids": synced}

    @app.post("/v1/flush")
    def flush(
        request: SidecarFlushRequest,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> dict[str, Any]:
        sc.flush(segment_id=request.segment_id, generation=request.generation)
        metrics.inc_flush()
        shard_manifest, _segment_manifests = sc.recall_layer.load_manifest_set()
        return {
            "active_segment_ids": (
                shard_manifest.active_segment_ids if shard_manifest is not None else []
            ),
        }

    @app.post("/v1/compact")
    def compact(
        request: SidecarCompactionRequest,
        sc: RecallLayerSidecar = Depends(require_auth),
    ) -> dict[str, Any]:
        result = sc.compact(
            output_segment_id=request.output_segment_id,
            generation=request.generation,
            min_segment_count=request.min_segment_count,
            max_total_rows=request.max_total_rows,
        )
        return {"compacted": result is not None, "result": result}

    @app.get("/metrics")
    def prometheus_metrics() -> Response:
        """Return collection and request counters in Prometheus text format."""
        col_stats = default_sidecar.recall_layer.collection_stats()
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


app = create_recalllayer_sidecar_app(config=load_sidecar_app_config_from_env())
