from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

from recalllayer.sidecar import PsycopgPostgresRepository, RecallLayerSidecar


@pytest.fixture()
def live_postgres_dsn() -> str:
    dsn = os.getenv("RECALLLAYER_LIVE_POSTGRES_DSN")
    if not dsn:
        pytest.skip("set RECALLLAYER_LIVE_POSTGRES_DSN to run live Postgres sidecar tests")
    return dsn


@pytest.fixture()
def postgres_documents_table(live_postgres_dsn: str) -> str:
    table_name = f"documents_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(live_postgres_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            create table {table_name} (
              id text primary key,
              title text not null,
              body text not null,
              region text not null,
              status text not null default 'published'
            )
            """
        )
        conn.commit()
    try:
        yield table_name
    finally:
        with psycopg.connect(live_postgres_dsn) as conn, conn.cursor() as cur:
            cur.execute(f"drop table if exists {table_name}")
            conn.commit()


@pytest.fixture()
def postgres_sidecar(tmp_path: Path, live_postgres_dsn: str, postgres_documents_table: str) -> RecallLayerSidecar:
    repo = PsycopgPostgresRepository.from_dsn(
        live_postgres_dsn,
        table_name=postgres_documents_table,
    )
    return RecallLayerSidecar(
        host_db=repo,
        root_dir=tmp_path,
        collection_id="recalllayer-live-postgres-test",
    )


def test_live_postgres_sidecar_query_hydrate_repair_and_restart(
    postgres_sidecar: RecallLayerSidecar,
) -> None:
    sidecar = postgres_sidecar
    sidecar.upsert_and_sync_document(
        document_id="1",
        title="Postgres retrieval guide",
        body="How to hydrate ids from a RecallLayer sidecar.",
        region="us",
    )
    sidecar.upsert_and_sync_document(
        document_id="2",
        title="Repair worker notes",
        body="Repair and backfill restore sidecar drift.",
        region="us",
    )

    initial = sidecar.search("postgres sidecar", top_k=2, region="us")
    assert initial["candidate_ids"] == ["document:1", "document:2"]
    assert [row["document_id"] for row in initial["hydrated_results"]] == ["1", "2"]

    sidecar.flush(segment_id="seg-1", generation=1)
    sidecar.unpublish_document("2")
    unpublished = sidecar.search("repair worker", top_k=2, region="us")
    assert unpublished["candidate_ids"] == []

    sidecar.write_source_record(
        document_id="3",
        title="Backfill worker",
        body="Rebuild the sidecar from host truth.",
        region="us",
    )
    backfilled = sidecar.backfill_from_host()
    assert "document:3" in backfilled

    restarted = sidecar.restart()
    after_restart = restarted.search("postgres backfill", top_k=3, region="us")
    assert [row["document_id"] for row in after_restart["hydrated_results"]] == ["1", "3"]


def test_live_postgres_sidecar_compaction_and_repair_converge(
    postgres_sidecar: RecallLayerSidecar,
) -> None:
    sidecar = postgres_sidecar
    sidecar.upsert_and_sync_document(
        document_id="1",
        title="Compaction guide",
        body="Segment compaction should preserve sidecar visibility.",
        region="us",
    )
    sidecar.flush(segment_id="seg-1", generation=1)
    sidecar.upsert_and_sync_document(
        document_id="2",
        title="Recovery notes",
        body="Restart should replay the expected tail writes.",
        region="us",
    )
    sidecar.flush(segment_id="seg-2", generation=2)

    result = sidecar.compact(output_segment_id="seg-merged", generation=3)
    assert result is not None
    assert result["active_segment_ids"] == ["seg-merged"]

    sidecar.host_db.delete_document("2")
    stale = sidecar.search("recovery notes", top_k=2, region="us")
    assert "document:2" in stale["candidate_ids"]
    assert stale["hydrated_results"] == []

    synced = sidecar.repair_documents(["2"])
    assert synced == ["document:2"]

    converged = sidecar.search("recovery notes", top_k=2, region="us")
    assert "document:2" not in converged["candidate_ids"]
