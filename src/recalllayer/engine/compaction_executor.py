from __future__ import annotations

from dataclasses import dataclass

from recalllayer.engine.compaction_planner import CompactionPlan, CompactionPlanner
from recalllayer.engine.compactor import CompactionArtifacts, LocalSegmentCompactor
from recalllayer.engine.manifest_validation import raise_for_manifest_issues, validate_manifest_set
from recalllayer.engine.retirement import apply_retirement, build_retirement_decision
from recalllayer.engine.segment_manifest_store import SegmentManifestStore
from recalllayer.model.manifest import SegmentManifest, SegmentState, ShardManifest


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
        artifacts.segment_manifest.state = SegmentState.ACTIVE
        self.segment_manifest_store.save(artifacts.segment_manifest)

        decision = build_retirement_decision(
            current_active_segment_ids=shard_manifest.active_segment_ids,
            replacement_segment_id=artifacts.segment_manifest.segment_id,
            retired_segment_ids=plan.candidate_segment_ids,
        )
        updated_existing_manifests = apply_retirement(segment_manifests, retired_segment_ids=decision.retired_segment_ids)
        updated_segment_manifests = [*updated_existing_manifests, artifacts.segment_manifest]
        for manifest in updated_existing_manifests:
            self.segment_manifest_store.save(manifest)

        updated_shard_manifest = shard_manifest.model_copy(
            update={
                "active_segment_ids": decision.next_active_segment_ids,
                "replay_from_write_epoch": max(
                    shard_manifest.replay_from_write_epoch,
                    artifacts.segment_manifest.max_write_epoch,
                ),
            }
        )
        issues = validate_manifest_set(shard_manifest=updated_shard_manifest, segment_manifests=updated_segment_manifests)
        raise_for_manifest_issues(issues)
        self.manifest_store.save(updated_shard_manifest)

        return CompactionExecutionResult(
            plan=plan,
            artifacts=artifacts,
            updated_shard_manifest=updated_shard_manifest,
            updated_segment_manifests=updated_segment_manifests,
            selected_source_segment_ids=list(plan.candidate_segment_ids),
        )
