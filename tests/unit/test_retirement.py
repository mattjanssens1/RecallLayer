from turboquant_db.engine.retirement import apply_retirement, build_retirement_decision
from turboquant_db.model.manifest import SegmentManifest, SegmentState


def _manifest(segment_id: str) -> SegmentManifest:
    return SegmentManifest(
        segment_id=segment_id,
        collection_id="documents",
        shard_id="shard-0",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
    )


def test_build_retirement_decision_replaces_old_active_segments() -> None:
    decision = build_retirement_decision(
        current_active_segment_ids=["seg-1", "seg-2"],
        replacement_segment_id="seg-3",
        retired_segment_ids=["seg-1", "seg-2"],
    )

    assert decision.next_active_segment_ids == ["seg-3"]
    assert decision.retired_segment_ids == ["seg-1", "seg-2"]


def test_apply_retirement_marks_selected_manifests_retired() -> None:
    updated = apply_retirement([_manifest("seg-1"), _manifest("seg-2")], retired_segment_ids=["seg-2"])
    states = {manifest.segment_id: manifest.state for manifest in updated}
    assert states["seg-1"] != SegmentState.RETIRED
    assert states["seg-2"] == SegmentState.RETIRED
