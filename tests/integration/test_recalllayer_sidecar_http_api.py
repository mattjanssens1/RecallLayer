from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from recalllayer.api.recalllayer_sidecar_app import (
    SidecarAppConfig,
    build_sidecar_from_config,
    create_recalllayer_sidecar_app,
)
from recalllayer.api.recalllayer_sidecar_schemas import (
    SidecarCompactionRequest,
    SidecarDocumentUpsertRequest,
    SidecarFlushRequest,
    SidecarQueryRequest,
    SidecarRepairRequest,
)


def route_endpoint(app, path: str, method: str):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"route not found: {method} {path}")


def test_recalllayer_sidecar_http_flow_covers_health_sync_query_repair_and_compaction(
    tmp_path: Path,
) -> None:
    app = create_recalllayer_sidecar_app(root_dir=tmp_path)

    health = route_endpoint(app, "/healthz", "GET")()
    assert health["status"] == "ok"
    assert health["api_key_enabled"] is False

    ready = route_endpoint(app, "/readyz", "GET")()
    assert ready["status"] == "ready"

    status_endpoint = route_endpoint(app, "/v1/status", "GET")
    status_payload = status_endpoint()
    assert status_payload["collection_id"] == "recalllayer-sidecar-demo"
    assert status_payload["known_shard_ids"] == ["shard-0"]

    upsert_document = route_endpoint(app, "/v1/documents/{document_id}", "PUT")
    query = route_endpoint(app, "/v1/query", "POST")
    flush = route_endpoint(app, "/v1/flush", "POST")
    compact = route_endpoint(app, "/v1/compact", "POST")
    repair = route_endpoint(app, "/v1/repair", "POST")

    upsert_one = upsert_document(
        "1",
        SidecarDocumentUpsertRequest(
            title="Postgres retrieval guide",
            body="How to hydrate ids from a sidecar search index.",
            region="us",
        ),
    )
    assert upsert_one["vector_id"] == "document:1"

    upsert_document(
        "2",
        SidecarDocumentUpsertRequest(
            title="Postgres repair worker",
            body="Repair jobs and backfill keep host truth ahead of the sidecar.",
            region="us",
        ),
    )

    initial = query(SidecarQueryRequest(query_text="postgres sidecar", top_k=2, region="us"))
    assert initial.candidate_ids == ["document:1", "document:2"]

    flushed = flush(SidecarFlushRequest(segment_id="seg-1", generation=1))
    assert flushed["active_segment_ids"] == ["seg-1"]

    upsert_document(
        "3",
        SidecarDocumentUpsertRequest(
            title="Postgres backfill flow",
            body="Backfill can rebuild a search sidecar from host rows.",
            region="us",
        ),
    )
    flush(SidecarFlushRequest(segment_id="seg-2", generation=2))

    compacted = compact(
        SidecarCompactionRequest(
            output_segment_id="seg-merged",
            generation=3,
            min_segment_count=2,
        )
    )
    assert compacted["compacted"] is True
    assert compacted["result"]["active_segment_ids"] == ["seg-merged"]

    app.state.sidecar.host_db.delete_document("2")

    stale = query(SidecarQueryRequest(query_text="postgres repair worker", top_k=2, region="us"))
    assert "document:2" in stale.candidate_ids
    assert [row.document_id for row in stale.hydrated_results] == ["1"]

    repaired = repair(SidecarRepairRequest())
    assert "document:2" in repaired["synced_vector_ids"]

    converged = query(
        SidecarQueryRequest(query_text="postgres repair worker", top_k=2, region="us")
    )
    assert "document:2" not in converged.candidate_ids

    restarted_app = create_recalllayer_sidecar_app(
        sidecar=app.state.sidecar.restart(),
        root_dir=tmp_path,
    )
    restarted_query = route_endpoint(restarted_app, "/v1/query", "POST")
    after_restart = restarted_query(
        SidecarQueryRequest(query_text="postgres sidecar", top_k=3, region="us")
    )
    assert [row.document_id for row in after_restart.hydrated_results] == ["1", "3"]


def test_sidecar_http_api_optional_api_key_is_enforced(tmp_path: Path) -> None:
    app = create_recalllayer_sidecar_app(
        config=SidecarAppConfig(root_dir=tmp_path, api_key="secret-key")
    )
    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["api_key_enabled"] is True

    blocked = client.post("/v1/query", json={"query_text": "postgres", "top_k": 1})
    assert blocked.status_code == 401

    allowed = client.post(
        "/v1/query",
        headers={"x-api-key": "secret-key"},
        json={"query_text": "postgres", "top_k": 1},
    )
    assert allowed.status_code == 200


def test_sidecar_http_config_can_build_inmemory_backend(tmp_path: Path) -> None:
    sidecar = build_sidecar_from_config(
        SidecarAppConfig(root_dir=tmp_path, collection_id="demo-http", host_repository="inmemory")
    )

    assert sidecar.collection_id == "demo-http"
    assert sidecar.host_db.__class__.__name__ == "InMemoryPostgresRepository"


def test_sidecar_http_config_requires_postgres_dsn_for_postgres_backend(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="RECALLLAYER_POSTGRES_DSN"):
        build_sidecar_from_config(
            SidecarAppConfig(root_dir=tmp_path, host_repository="postgres")
        )


def test_sidecar_http_config_rejects_unknown_backend(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="unsupported RECALLLAYER_HOST_REPOSITORY"):
        build_sidecar_from_config(
            SidecarAppConfig(root_dir=tmp_path, host_repository="sqlite")
        )
