from dataclasses import dataclass

from turboquant_db.model.manifest import SegmentManifest, SegmentState


@dataclass(slots=True)
class CompactionPlan:
    candidate_segment_ids: list[str]
    total_rows: int
    reason: str


class CompactionPlanner:
    def __init__(self, *, min_segment_count: int = 2, max_total_rows: int = 50000) -> None:
        self.min_segment_count = min_segment_count
        self.max_total_rows = max_total_rows

    def plan(self, manifests: list[SegmentManifest]) -> CompactionPlan | None:
        candidates = [manifest for manifest in manifests if manifest.state in {SegmentState.SEALED, SegmentState.ACTIVE}]
        candidates.sort(key=lambda item: (item.generation, item.segment_id))
        if len(candidates) < self.min_segment_count:
            return None

        selected: list[SegmentManifest] = []
        total_rows = 0
        for manifest in candidates:
            next_total = total_rows + manifest.row_count
            if selected and next_total > self.max_total_rows:
                break
            selected.append(manifest)
            total_rows = next_total

        if len(selected) < self.min_segment_count:
            return None
        return CompactionPlan(
            candidate_segment_ids=[manifest.segment_id for manifest in selected],
            total_rows=total_rows,
            reason="segment-count-and-row-budget",
        )
