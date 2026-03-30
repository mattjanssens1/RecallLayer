from pathlib import Path

from turboquant_db.engine.recovery_audit import build_recovery_audit
from turboquant_db.engine.write_log import WriteLog


def test_build_recovery_audit_groups_entries_by_collection(tmp_path: Path) -> None:
    log = WriteLog(tmp_path / "write_log.jsonl")
    log.append_upsert(collection_id="documents", vector_id="a", write_epoch=1, embedding=[1.0])
    log.append_delete(collection_id="documents", vector_id="a", write_epoch=2)
    log.append_upsert(collection_id="events", vector_id="evt-1", write_epoch=3, embedding=[0.5])

    rows = build_recovery_audit(log)
    by_collection = {row.collection_id: row for row in rows}

    assert by_collection["documents"].total_entries == 2
    assert by_collection["documents"].upsert_count == 1
    assert by_collection["documents"].delete_count == 1
    assert by_collection["documents"].latest_write_epoch == 2
    assert by_collection["documents"].distinct_vector_count == 1
    assert by_collection["events"].latest_write_epoch == 3
