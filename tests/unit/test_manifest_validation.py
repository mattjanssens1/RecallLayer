from turboquant_db.engine.manifest_validation import raise_for_manifest_issues, validate_manifest_set
from turboquant_db.model.manifest import SegmentManifest, SegmentState, ShardManifest


def test_validate_manifest_set_flags_missing_and_retired_active_segments() -> None:
    shard = ShardManifest(shard_id="shard-0", collection_id="documents", active_segment_ids=["seg-1", "seg-2"])
    manifests = [
        SegmentManifest(
            segment_id="seg-1",
            collection_id="documents",
            shard_id="shard-0",
            generation=1,
            state=SegmentState.RETIRED,
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
        )
    ]

    issues = validate_manifest_set(shard_manifest=shard, segment_manifests=manifests)
    messages = {(issue.message, issue.segment_id) for issue in issues}

    assert ("retired segment still active", "seg-1") in messages
    assert ("active segment missing manifest", "seg-2") in messages


def test_validate_manifest_set_flags_collection_and_row_count_mismatches() -> None:
    shard = ShardManifest(shard_id="shard-0", collection_id="documents", active_segment_ids=["seg-1"])
    manifests = [
        SegmentManifest(
            segment_id="seg-1",
            collection_id="other",
            shard_id="shard-0",
            generation=1,
            row_count=3,
            live_row_count=4,
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
        )
    ]

    issues = validate_manifest_set(shard_manifest=shard, segment_manifests=manifests)
    messages = {(issue.message, issue.segment_id) for issue in issues}

    assert ("collection mismatch", "seg-1") in messages
    assert ("live rows exceed row count", "seg-1") in messages


def test_validate_manifest_set_warns_for_missing_activation_timestamps() -> None:
    shard = ShardManifest(shard_id="shard-0", collection_id="documents", active_segment_ids=["seg-1"])
    manifests = [
        SegmentManifest(
            segment_id="seg-1",
            collection_id="documents",
            shard_id="shard-0",
            generation=1,
            state=SegmentState.ACTIVE,
            row_count=2,
            live_row_count=2,
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
        )
    ]

    issues = validate_manifest_set(shard_manifest=shard, segment_manifests=manifests)
    messages = {(issue.level, issue.message, issue.segment_id) for issue in issues}

    assert ("warn", "sealed segment missing sealed_at", "seg-1") in messages
    assert ("warn", "active segment missing activated_at", "seg-1") in messages


def test_raise_for_manifest_issues_raises_only_on_errors() -> None:
    raise_for_manifest_issues([])
    raise_for_manifest_issues([
        type('Issue', (), {'level': 'warn', 'message': 'warn-only', 'segment_id': 'seg-1'})(),
    ])

    try:
        raise_for_manifest_issues([
            type('Issue', (), {'level': 'error', 'message': 'broken', 'segment_id': 'seg-2'})(),
        ])
    except ValueError as exc:
        assert 'broken:seg-2' in str(exc)
    else:
        raise AssertionError('expected ValueError for error-level manifest issue')
