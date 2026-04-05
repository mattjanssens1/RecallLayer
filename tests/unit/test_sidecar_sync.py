from pathlib import Path

import pytest

from recalllayer.sidecar import InMemoryPostgres, RecallLayerSidecar
from recalllayer.sidecar_sync import (
    InMemorySidecarSyncOutbox,
    RecallLayerSyncWorker,
    apply_host_unpublish_with_outbox,
    apply_host_write_with_outbox,
)


def test_outbox_worker_applies_host_truth_to_recalllayer(tmp_path: Path) -> None:
    sidecar = RecallLayerSidecar(host_db=InMemoryPostgres(), root_dir=tmp_path)
    outbox = InMemorySidecarSyncOutbox()
    worker = RecallLayerSyncWorker(sidecar=sidecar, outbox=outbox)

    apply_host_write_with_outbox(
        sidecar=sidecar,
        outbox=outbox,
        document_id="1",
        title="Postgres retrieval guide",
        body="Host DB truth emits an event that syncs RecallLayer.",
        region="us",
    )

    assert sidecar.search("postgres retrieval", top_k=1, region="us")["candidate_ids"] == []

    synced = worker.process_pending()

    assert synced == ["document:1"]
    result = sidecar.search("postgres retrieval", top_k=1, region="us")
    assert result["candidate_ids"] == ["document:1"]


def test_outbox_worker_can_unpublish_after_flush(tmp_path: Path) -> None:
    sidecar = RecallLayerSidecar(host_db=InMemoryPostgres(), root_dir=tmp_path)
    outbox = InMemorySidecarSyncOutbox()
    worker = RecallLayerSyncWorker(sidecar=sidecar, outbox=outbox)

    apply_host_write_with_outbox(
        sidecar=sidecar,
        outbox=outbox,
        document_id="1",
        title="Postgres retrieval guide",
        body="Flush then unpublish through the outbox path.",
        region="us",
    )
    worker.process_pending()
    sidecar.flush(segment_id="seg-1", generation=1)

    apply_host_unpublish_with_outbox(sidecar=sidecar, outbox=outbox, document_id="1")
    worker.process_pending()

    result = sidecar.search("postgres retrieval", top_k=1, region="us")
    assert result["candidate_ids"] == []
    assert result["hydrated_results"] == []


def test_outbox_worker_marks_failed_for_unknown_operation(tmp_path: Path) -> None:
    sidecar = RecallLayerSidecar(host_db=InMemoryPostgres(), root_dir=tmp_path)
    outbox = InMemorySidecarSyncOutbox()
    worker = RecallLayerSyncWorker(sidecar=sidecar, outbox=outbox)

    event = outbox.enqueue(document_id="1", operation="mystery")

    with pytest.raises(ValueError, match="unsupported outbox operation"):
        worker.process_pending()

    assert outbox._get(event.event_id).status == "failed"
