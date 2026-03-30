from turboquant_db.model.manifest import SegmentManifest, SegmentState, ShardManifest, ShardState


def test_segment_manifest_defaults() -> None:
    manifest = SegmentManifest(
        segment_id="seg-1",
        collection_id="documents",
        shard_id="shard-0",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
    )

    assert manifest.state == SegmentState.BUILDING
    assert manifest.row_count == 0
    assert manifest.live_row_count == 0


def test_shard_manifest_defaults() -> None:
    shard = ShardManifest(
        shard_id="shard-0",
        collection_id="documents",
    )

    assert shard.state == ShardState.ACTIVE
    assert shard.active_segment_ids == []
