"""Background compaction policy — synchronous "check and maybe compact" helper."""
from __future__ import annotations

from dataclasses import dataclass

from recalllayer.engine.compaction_executor import CompactionExecutionResult, CompactionExecutor


@dataclass(slots=True)
class CompactionThresholds:
    """Thresholds that trigger auto-compaction."""

    min_segment_count: int = 2
    """Compact when there are at least this many active segments."""
    min_delete_ratio: float = 0.2
    """Compact when the delete ratio is at or above this value."""
    max_row_count: int = 100_000
    """Compact when total rows across segments exceed this value."""


class CompactionPolicy:
    """Wraps a :class:`CompactionExecutor` and decides whether to compact.

    Usage::

        policy = CompactionPolicy(executor=my_executor, thresholds=CompactionThresholds())
        result = policy.maybe_compact(collection_id="docs", shard_id="shard-0")
        # result is CompactionExecutionResult or None
    """

    def __init__(
        self,
        *,
        executor: CompactionExecutor,
        thresholds: CompactionThresholds | None = None,
    ) -> None:
        self.executor = executor
        self.thresholds = thresholds or CompactionThresholds()

    def _should_compact(
        self,
        *,
        collection_id: str,
        shard_id: str,
    ) -> tuple[bool, str]:
        """Return (should_compact, reason) based on current shard state."""
        manifest_store = self.executor.manifest_store
        segment_manifest_store = self.executor.segment_manifest_store

        shard_manifest = manifest_store.load(collection_id=collection_id, shard_id=shard_id)
        if shard_manifest is None:
            return False, "no shard manifest"

        from recalllayer.model.manifest import SegmentState

        segment_manifests = segment_manifest_store.list_manifests(
            collection_id=collection_id, shard_id=shard_id
        )
        active_ids = set(shard_manifest.active_segment_ids)
        active = [m for m in segment_manifests if m.segment_id in active_ids and m.state in {SegmentState.ACTIVE, SegmentState.SEALED}]

        segment_count = len(active)
        total_rows = sum(m.row_count for m in active)
        live_rows = sum(m.live_row_count for m in active)
        delete_ratio = (1.0 - live_rows / total_rows) if total_rows > 0 else 0.0

        t = self.thresholds
        if segment_count >= t.min_segment_count and delete_ratio >= t.min_delete_ratio:
            return True, f"delete_ratio={delete_ratio:.3f} >= {t.min_delete_ratio}"
        if segment_count >= t.min_segment_count and total_rows >= t.max_row_count:
            return True, f"total_rows={total_rows} >= {t.max_row_count}"
        if segment_count > t.min_segment_count:
            return True, f"segment_count={segment_count} > {t.min_segment_count}"
        return False, f"segment_count={segment_count}, delete_ratio={delete_ratio:.3f}, total_rows={total_rows}"

    def maybe_compact(
        self,
        *,
        collection_id: str,
        shard_id: str = "shard-0",
        output_segment_id: str = "seg-compacted",
        generation: int = 1,
        embedding_version: str = "embed-v1",
        quantizer_version: str = "tq-v0",
    ) -> CompactionExecutionResult | None:
        """Run compaction if thresholds are exceeded; return result or None."""
        should, _reason = self._should_compact(collection_id=collection_id, shard_id=shard_id)
        if not should:
            return None
        return self.executor.compact_shard(
            collection_id=collection_id,
            shard_id=shard_id,
            output_segment_id=output_segment_id,
            generation=generation,
            embedding_version=embedding_version,
            quantizer_version=quantizer_version,
        )
