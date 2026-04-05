from pathlib import Path

from turboquant_db.sidecar import InMemoryPostgres, RecallLayerSidecar, build_demo_state


def test_sidecar_flow_returns_candidate_ids_then_hydrates_from_host_db(tmp_path: Path) -> None:
    app = build_demo_state(tmp_path)

    result = app.search("postgres search sidecar", top_k=2, region="us")

    assert result["candidate_ids"]
    assert result["candidate_ids"][0] == "document:1"
    assert [row["document_id"] for row in result["hydrated_results"]] == ["1", "2"]
    assert result["hydrated_results"][0]["title"] == "Postgres retrieval guide"

    app.flush(segment_id="seg-1", generation=1)
    flushed = app.search("postgres search sidecar", top_k=2, region="us")
    assert flushed["candidate_ids"][:2] == result["candidate_ids"][:2]


def test_sidecar_delete_and_restart_recovery_keep_unpublished_rows_hidden(tmp_path: Path) -> None:
    app = build_demo_state(tmp_path)
    app.flush(segment_id="seg-1", generation=1)

    app.unpublish_document("1")

    before_restart = app.search("postgres search sidecar", top_k=2, region="us")
    assert before_restart["candidate_ids"] == ["document:2"]
    assert [row["document_id"] for row in before_restart["hydrated_results"]] == ["2"]

    restarted = app.restart()
    after_restart = restarted.search("postgres search sidecar", top_k=2, region="us")
    assert after_restart["candidate_ids"] == ["document:2"]
    assert [row["document_id"] for row in after_restart["hydrated_results"]] == ["2"]


def test_host_hydration_can_drop_stale_sidecar_hits_and_repair_converges(tmp_path: Path) -> None:
    host_db = InMemoryPostgres()
    app = RecallLayerSidecar(host_db=host_db, root_dir=tmp_path)
    app.write_source_record(
        document_id="1",
        title="Postgres retrieval guide",
        body="How to hydrate ids from a sidecar search index.",
        region="us",
    )
    app.sync_document("1")

    stale = app.search("postgres search sidecar", top_k=1, region="us")
    assert stale["candidate_ids"] == ["document:1"]
    assert [row["document_id"] for row in stale["hydrated_results"]] == ["1"]

    host_db.delete_document("1")

    mismatched = app.search("postgres search sidecar", top_k=1, region="us")
    assert mismatched["candidate_ids"] == ["document:1"]
    assert mismatched["hydrated_results"] == []

    app.repair_documents(["1"])
    repaired = app.search("postgres search sidecar", top_k=1, region="us")
    assert repaired["candidate_ids"] == []
    assert repaired["hydrated_results"] == []


def test_sidecar_compaction_and_restart_keep_query_and_hydration_stable(tmp_path: Path) -> None:
    app = build_demo_state(tmp_path)
    app.flush(segment_id="seg-1", generation=1)

    app.upsert_and_sync_document(
        document_id="4",
        title="Postgres sync worker",
        body="Repair and backfill workers keep sidecar state aligned.",
        region="us",
    )
    app.flush(segment_id="seg-2", generation=2)

    before_compaction = app.search("postgres repair sidecar", top_k=3, region="us")
    compaction = app.compact(output_segment_id="seg-merged", generation=3)

    assert compaction is not None
    assert compaction["active_segment_ids"] == ["seg-merged"]
    assert compaction["selected_source_segment_ids"] == ["seg-1", "seg-2"]

    restarted = app.restart()
    after_restart = restarted.search("postgres repair sidecar", top_k=3, region="us")

    assert after_restart["candidate_ids"] == before_compaction["candidate_ids"]
    assert [row["document_id"] for row in after_restart["hydrated_results"]] == [
        row["document_id"] for row in before_compaction["hydrated_results"]
    ]
