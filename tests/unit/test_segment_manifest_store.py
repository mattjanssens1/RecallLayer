from pathlib import Path

from recalllayer.engine.segment_manifest_store import SegmentManifestStore
from recalllayer.model.manifest import SegmentManifest, SegmentState


def test_segment_manifest_store_round_trips_manifest(tmp_path: Path) -> None:
    store = SegmentManifestStore(tmp_path)
    manifest = SegmentManifest(
        segment_id="seg-1",
        collection_id="documents",
        shard_id="shard-0",
        generation=3,
        state=SegmentState.ACTIVE,
        row_count=10,
        live_row_count=9,
        deleted_row_count=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        min_write_epoch=2,
        max_write_epoch=11,
    )

    store.save(manifest)
    loaded = store.load(collection_id="documents", shard_id="shard-0", segment_id="seg-1")

    assert loaded is not None
    assert loaded.segment_id == manifest.segment_id
    assert loaded.state == SegmentState.ACTIVE
    assert loaded.max_write_epoch == 11


def test_segment_manifest_store_lists_sorted_manifests(tmp_path: Path) -> None:
    store = SegmentManifestStore(tmp_path)
    for segment_id in ["seg-2", "seg-1"]:
        store.save(
            SegmentManifest(
                segment_id=segment_id,
                collection_id="documents",
                shard_id="shard-0",
                generation=1,
                embedding_version="embed-v1",
                quantizer_version="tq-v0",
            )
        )

    manifests = store.list_manifests(collection_id="documents", shard_id="shard-0")
    assert [manifest.segment_id for manifest in manifests] == ["seg-1", "seg-2"]
