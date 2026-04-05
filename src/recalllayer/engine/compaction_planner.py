from __future__ import annotations

from dataclasses import dataclass

from recalllayer.model.manifest import SegmentManifest, SegmentState


@dataclass(slots=True)
class CompactionPlan:
    candidate_segment_ids: list[str]
    total_rows: int
    reason: str


def _shard_delete_ratio(manifests: list[SegmentManifest]) -> float:
    """Compute delete ratio across a set of manifests."""
    total = sum(m.row_count for m in manifests)
    live = sum(m.live_row_count for m in manifests)
    if total == 0:
        return 0.0
    return 1.0 - live / total


def compaction_eligibility_score(
    manifests: list[SegmentManifest],
    *,
    min_segment_count: int,
    max_total_rows: int,
    delete_ratio_weight: float = 2.0,
) -> float:
    """Return a score >= 0 indicating how urgently this shard needs compaction.

    Score is 0 when the shard does not qualify (< min_segment_count segments).
    Higher score = more urgent.

    Components:
    - segment count relative to min_segment_count
    - delete ratio (weighted)
    - total rows relative to max_total_rows
    """
    n = len(manifests)
    if n < min_segment_count:
        return 0.0
    total_rows = sum(m.row_count for m in manifests)
    delete_ratio = _shard_delete_ratio(manifests)
    count_score = (n - min_segment_count + 1)
    row_score = total_rows / max(max_total_rows, 1)
    return count_score + delete_ratio_weight * delete_ratio + row_score


class CompactionPlanner:
    def __init__(
        self,
        *,
        min_segment_count: int = 2,
        max_total_rows: int = 50000,
        min_delete_ratio: float = 0.0,
        delete_ratio_weight: float = 2.0,
    ) -> None:
        self.min_segment_count = min_segment_count
        self.max_total_rows = max_total_rows
        self.min_delete_ratio = min_delete_ratio
        self.delete_ratio_weight = delete_ratio_weight

    def plan(self, manifests: list[SegmentManifest]) -> CompactionPlan | None:
        candidates = [manifest for manifest in manifests if manifest.state in {SegmentState.SEALED, SegmentState.ACTIVE}]
        candidates.sort(key=lambda item: (item.generation, item.segment_id))
        if len(candidates) < self.min_segment_count:
            return None

        # Skip shards where delete ratio is below threshold
        delete_ratio = _shard_delete_ratio(candidates)
        if delete_ratio < self.min_delete_ratio:
            # Only skip if there are exactly the minimum number of segments
            # (i.e., compaction is driven purely by deletes, not count pressure).
            if len(candidates) < self.min_segment_count + 1:
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

        score = compaction_eligibility_score(
            selected,
            min_segment_count=self.min_segment_count,
            max_total_rows=self.max_total_rows,
            delete_ratio_weight=self.delete_ratio_weight,
        )
        reason = f"eligibility-score={score:.3f} delete-ratio={delete_ratio:.3f}"
        return CompactionPlan(
            candidate_segment_ids=[manifest.segment_id for manifest in selected],
            total_rows=total_rows,
            reason=reason,
        )
