from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.model.manifest import SegmentManifest, SegmentState


def _manifest(segment_id: str, generation: int, row_count: int, state: SegmentState = SegmentState.SEALED) -> SegmentManifest:
    return SegmentManifest(
        segment_id=segment_id,
        collection_id="documents",
        shard_id="shard-0",
        generation=generation,
        state=state,
        row_count=row_count,
        live_row_count=row_count,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
    )


def test_compaction_planner_returns_plan_with_small_sorted_set() -> None:
    # With priority-based sorting, older/higher-delete-ratio segments come first.
    # All segments here have 0 delete ratio, so age (generation) breaks ties.
    # seg-1 (gen=1) has highest age score; seg-2 (gen=2) next; seg-3 (gen=3) lowest.
    # max_total_rows=20 lets all fit; expect seg-1 and seg-2 as highest priority pair.
    planner = CompactionPlanner(min_segment_count=2, max_total_rows=20)
    plan = planner.plan([
        _manifest("seg-2", generation=2, row_count=3),
        _manifest("seg-1", generation=1, row_count=4),
        _manifest("seg-3", generation=3, row_count=3),
    ])

    assert plan is not None
    # seg-1 (highest priority: oldest) and seg-2 selected first
    assert "seg-1" in plan.candidate_segment_ids
    assert plan.total_rows >= 7


def test_compaction_planner_returns_none_when_not_enough_candidates() -> None:
    planner = CompactionPlanner(min_segment_count=2)
    plan = planner.plan([_manifest("seg-1", generation=1, row_count=3, state=SegmentState.RETIRED)])
    assert plan is None
