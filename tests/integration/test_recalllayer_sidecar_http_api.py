from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from recalllayer.api.recalllayer_sidecar_app import (
    SidecarAppConfig,
    build_sidecar_from_config,
    create_recalllayer_sidecar_app,
)
from recalllayer.api.recalllayer_sidecar_schemas import SidecarFlushRequest


def test_recalllayer_sidecar_http_flow_covers_health_sync_query_repair_and_compaction(
    tmp_path: Path,
) -> None:
    app = create_recalllayer_sidecar_app(root_dir=tmp_path)
    client = TestClient(app)

    health = client.get("/healthz").json()
    assert health["status"] == "ok"
    assert health["api_key_enabled"] is False

    ready = client.get("/readyz").json()
    assert ready["status"] == "ready"

    status_payload = client.get("/v1/status").json()
    assert status_payload["collection_id"] == "recalllayer-sidecar-demo"
    assert status_payload["known_shard_ids"] == ["shard-0"]

    upsert_one = client.put(
        "/v1/documents/1",
        json={
            "title": "Postgres retrieval guide",
            "body": "How to hydrate ids from a sidecar search index.",
            "region": "us",
            "status": "published",
        },
    ).json()
    assert upsert_one["vector_id"] == "document:1"

    client.put(
        "/v1/documents/2",
        json={
            "title": "Postgres repair worker",
            "body": "Repair jobs and backfill keep host truth ahead of the sidecar.",
            "region": "us",
            "status": "published",
        },
    )

    initial = client.post(
        "/v1/query", json={"query_text": "postgres sidecar", "top_k": 2, "region": "us"}
    ).json()
    assert initial["candidate_ids"] == ["document:1", "document:2"]

    flushed = client.post(
        "/v1/flush", json={"segment_id": "seg-1", "generation": 1}
    ).json()
    assert flushed["active_segment_ids"] == ["seg-1"]

    client.put(
        "/v1/documents/3",
        json={
            "title": "Postgres backfill flow",
            "body": "Backfill can rebuild a search sidecar from host rows.",
            "region": "us",
            "status": "published",
        },
    )
    client.post("/v1/flush", json={"segment_id": "seg-2", "generation": 2})

    compacted = client.post(
        "/v1/compact",
        json={"output_segment_id": "seg-merged", "generation": 3, "min_segment_count": 2},
    ).json()
    assert compacted["compacted"] is True
    assert compacted["result"]["active_segment_ids"] == ["seg-merged"]

    # Delete doc 2 from host DB directly (simulates external deletion)
    app.state.sidecar.host_db.delete_document("2")

    stale = client.post(
        "/v1/query", json={"query_text": "postgres repair worker", "top_k": 2, "region": "us"}
    ).json()
    assert "document:2" in stale["candidate_ids"]
    hydrated_ids = [row["document_id"] for row in stale["hydrated_results"]]
    assert hydrated_ids == ["1"]

    repaired = client.post("/v1/repair", json={}).json()
    assert "document:2" in repaired["synced_vector_ids"]

    converged = client.post(
        "/v1/query", json={"query_text": "postgres repair worker", "top_k": 2, "region": "us"}
    ).json()
    assert "document:2" not in converged["candidate_ids"]

    # Restart: rebuild from persisted state
    restarted_app = create_recalllayer_sidecar_app(
        sidecar=app.state.sidecar.restart(),
        root_dir=tmp_path,
    )
    restarted_client = TestClient(restarted_app)
    after_restart = restarted_client.post(
        "/v1/query", json={"query_text": "postgres sidecar", "top_k": 3, "region": "us"}
    ).json()
    doc_ids = [row["document_id"] for row in after_restart["hydrated_results"]]
    assert doc_ids == ["1", "3"]


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
