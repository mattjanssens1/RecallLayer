from pathlib import Path

from fastapi.routing import APIRoute

from turboquant_db.api.recalllayer_sidecar_app import create_recalllayer_sidecar_app
from turboquant_db.api.recalllayer_sidecar_schemas import (
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
