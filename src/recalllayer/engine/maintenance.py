from __future__ import annotations

from dataclasses import dataclass

from recalllayer.engine.compaction_executor import CompactionExecutionResult, CompactionExecutor
from recalllayer.model.manifest import SegmentState


@dataclass(slots=True)
class MaintenanceCandidate:
    shard_id: str
    segment_count: int
    total_rows: int
    delete_ratio: float
    mutable_rows: int
    score: float
    reason: str


@dataclass(slots=True)
class MaintenanceThresholds:
    min_segment_count: int = 2
    min_delete_ratio: float = 0.15
    max_total_rows: int = 100_000
    min_score: float = 0.25
    mutable_pressure_weight: float = 0.5
    delete_ratio_weight: float = 2.0
    segment_count_weight: float = 1.0
    row_pressure_weight: float = 1.0


class AdaptiveMaintenancePlanner:
    def __init__(self, *, thresholds: MaintenanceThresholds | None = None) -> None:
        self.thresholds = thresholds or MaintenanceThresholds()

    def score_shard(
        self,
        *,
        shard_id: str,
        segment_count: int,
        total_rows: int,
        live_rows: int,
        mutable_rows: int,
    ) -> MaintenanceCandidate:
        delete_ratio = (1.0 - live_rows / total_rows) if total_rows > 0 else 0.0
        t = self.thresholds
        segment_pressure = max(0, segment_count - t.min_segment_count + 1)
        row_pressure = total_rows / max(t.max_total_rows, 1)
        mutable_pressure = mutable_rows / max(t.max_total_rows, 1)
        score = (
            t.segment_count_weight * segment_pressure
            + t.delete_ratio_weight * delete_ratio
            + t.row_pressure_weight * row_pressure
            + t.mutable_pressure_weight * mutable_pressure
        )
        reason = (
            f"segments={segment_count} delete_ratio={delete_ratio:.3f} "
            f"rows={total_rows} mutable_rows={mutable_rows} score={score:.3f}"
        )
        return MaintenanceCandidate(
            shard_id=shard_id,
            segment_count=segment_count,
            total_rows=total_rows,
            delete_ratio=delete_ratio,
            mutable_rows=mutable_rows,
            score=score,
            reason=reason,
        )

    def rank_candidates(self, snapshots: list[MaintenanceCandidate]) -> list[MaintenanceCandidate]:
        eligible = [
            candidate
            for candidate in snapshots
            if candidate.segment_count >= self.thresholds.min_segment_count
            and (
                candidate.delete_ratio >= self.thresholds.min_delete_ratio
                or candidate.total_rows >= self.thresholds.max_total_rows
                or candidate.mutable_rows > 0
                or candidate.segment_count > self.thresholds.min_segment_count
            )
            and candidate.score >= self.thresholds.min_score
        ]
        return sorted(eligible, key=lambda item: item.score, reverse=True)


class AdaptiveMaintenancePolicy:
    def __init__(
        self,
        *,
        executor: CompactionExecutor,
        planner: AdaptiveMaintenancePlanner | None = None,
        mutable_buffer_provider=None,
    ) -> None:
        self.executor = executor
        self.planner = planner or AdaptiveMaintenancePlanner()
        self.mutable_buffer_provider = mutable_buffer_provider

    def snapshot_shards(self, *, collection_id: str) -> list[MaintenanceCandidate]:
        manifests_dir = self.executor.manifest_store.root_dir / collection_id
        shard_ids: set[str] = set()
        if manifests_dir.exists():
            for path in manifests_dir.iterdir():
                if path.name.endswith(".manifest.json"):
                    shard_ids.add(path.name.replace(".manifest.json", ""))

        snapshots: list[MaintenanceCandidate] = []
        for shard_id in sorted(shard_ids):
            shard_manifest = self.executor.manifest_store.load(
                collection_id=collection_id,
                shard_id=shard_id,
            )
            if shard_manifest is None:
                continue
            segment_manifests = self.executor.segment_manifest_store.list_manifests(
                collection_id=collection_id,
                shard_id=shard_id,
            )
            active_ids = set(shard_manifest.active_segment_ids)
            active = [
                manifest
                for manifest in segment_manifests
                if manifest.segment_id in active_ids
                and manifest.state in {SegmentState.ACTIVE, SegmentState.SEALED}
            ]
            mutable_rows = 0
            if self.mutable_buffer_provider is not None:
                mutable_rows = int(self.mutable_buffer_provider(shard_id))
            snapshots.append(
                self.planner.score_shard(
                    shard_id=shard_id,
                    segment_count=len(active),
                    total_rows=sum(manifest.row_count for manifest in active),
                    live_rows=sum(manifest.live_row_count for manifest in active),
                    mutable_rows=mutable_rows,
                )
            )
        return snapshots

    def maybe_compact_best(
        self,
        *,
        collection_id: str,
        output_segment_prefix: str = "seg-maintained",
        generation: int = 1,
        embedding_version: str = "embed-v1",
        quantizer_version: str = "tq-v0",
        n_ivf_clusters: int | None = None,
    ) -> CompactionExecutionResult | None:
        ranked = self.planner.rank_candidates(self.snapshot_shards(collection_id=collection_id))
        if not ranked:
            return None
        best = ranked[0]
        return self.executor.compact_shard(
            collection_id=collection_id,
            shard_id=best.shard_id,
            output_segment_id=f"{output_segment_prefix}-{best.shard_id}",
            generation=generation,
            embedding_version=embedding_version,
            quantizer_version=quantizer_version,
            n_ivf_clusters=n_ivf_clusters,
        )
