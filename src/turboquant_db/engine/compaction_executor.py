from __future__ import annotations

from dataclasses import dataclass

from turboquant_db.engine.compaction_planner import CompactionPlan, CompactionPlanner
from turboquant_db.engine.compactor import CompactionArtifacts, LocalSegmentCompactor
from turboquant_db.engine.segment_manifest_store import SegmentManifestStore
from turboquant_db.model.manifest import SegmentManifest, SegmentState, ShardManifest


@dataclass(slots=True)
class CompactionExecutionResult:
    plan: CompactionPlan
    artifacts: CompactionArtifacts
    updated_shard_manifest: ShardManifest
    updated_segment_manifests: list[SegmentManifest]
    selected_source_segment_ids: list[str]


class CompactionExecutor:
    def __init__(
        self,
        *,
        planner: CompactionPlanner,
        compactor: LocalSegmentCompactor,
        manifest_store,
        segment_manifest_store: SegmentManifestStore,
    ) -> None:
        self.planner = planner
        self.compactor = compactor
        self.manifest_store = manifest_store
        self.segment_manifest_store = segment_manifest_store

    def compact_shard(
        self,
        *,
        collection_id: str,
        shard_id: str = "shard-0",
        output_segment_id: str = "seg-compacted",
        generation: int = 1,
        embedding_version: str = "embed-v1",
        quantizer_version: str = "tq-v0",
    ) -> CompactionExecutionResult | None:
        shard_manifest = self.manifest_store.load(collection_id=collection_id, shard_id=shard_id)
        if shard_manifest is None:
            return None

        segment_manifests = self.segment_manifest_store.list_manifests(collection_id=collection_id, shard_id=shard_id)
        active_segment_ids = set(shard_manifest.active_segment_ids)
        eligible_manifests = [
            manifest
            for manifest in segment_manifests
            if manifest.segment_id in active_segment_ids and manifest.state in {SegmentState.ACTIVE, SegmentState.SEALED}
        ]
        plan = self.planner.plan(eligible_manifests)
        if plan is None:
            return None

        artifacts = self.compactor.compact(
            collection_id=collection_id,
            shard_id=shard_id,
            output_segment_id=output_segment_id,
            generation=generation,
            embedding_version=embedding_version,
            quantizer_version=quantizer_version,
            source_segment_ids=plan.candidate_segment_ids,
        )
        artifacts.segment_manifest.state = SegmentState.SEALED
        self.segment_manifest_store.save(artifacts.segment_manifest)

        return CompactionExecutionResult(
            plan=plan,
            artifacts=artifacts,
            updated_shard_manifest=shard_manifest,
            updated_segment_manifests=[*segment_manifests, artifacts.segment_manifest],
            selected_source_segment_ids=list(plan.candidate_segment_ids),
        )
