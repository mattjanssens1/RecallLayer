from pathlib import Path

from turboquant_db.engine.segment_gc import plan_segment_garbage_collection
from turboquant_db.model.manifest import SegmentManifest, SegmentState


def _manifest(segment_id: str, state: SegmentState) -> SegmentManifest:
    return SegmentManifest(
        segment_id=segment_id,
        collection_id="documents",
        shard_id="shard-0",
        generation=1,
        state=state,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
    )


def test_plan_segment_garbage_collection_returns_only_retired_segments(tmp_path: Path) -> None:
    candidates = plan_segment_garbage_collection(
        manifests=[_manifest("seg-1", SegmentState.RETIRED), _manifest("seg-2", SegmentState.ACTIVE)],
        segments_root=tmp_path,
    )

    assert [candidate.segment_id for candidate in candidates] == ["seg-1"]
    assert candidates[0].segment_path == tmp_path / "documents" / "shard-0" / "seg-1.segment.jsonl"
    assert candidates[0].manifest_path == tmp_path / "documents" / "shard-0" / "seg-1.manifest.json"
