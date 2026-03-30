from __future__ import annotations

from dataclasses import dataclass

from turboquant_db.model.manifest import SegmentManifest, SegmentState, ShardManifest


@dataclass(slots=True)
class ManifestValidationIssue:
    level: str
    message: str
    segment_id: str | None = None


def validate_manifest_set(
    *,
    shard_manifest: ShardManifest,
    segment_manifests: list[SegmentManifest],
) -> list[ManifestValidationIssue]:
    issues: list[ManifestValidationIssue] = []
    seen_segment_ids: set[str] = set()
    by_segment_id: dict[str, SegmentManifest] = {}

    for manifest in segment_manifests:
        if manifest.segment_id in seen_segment_ids:
            issues.append(ManifestValidationIssue(level="error", message="duplicate segment manifest", segment_id=manifest.segment_id))
        seen_segment_ids.add(manifest.segment_id)
        by_segment_id[manifest.segment_id] = manifest

        if manifest.collection_id != shard_manifest.collection_id:
            issues.append(ManifestValidationIssue(level="error", message="collection mismatch", segment_id=manifest.segment_id))
        if manifest.shard_id != shard_manifest.shard_id:
            issues.append(ManifestValidationIssue(level="error", message="shard mismatch", segment_id=manifest.segment_id))
        if manifest.live_row_count > manifest.row_count:
            issues.append(ManifestValidationIssue(level="error", message="live rows exceed row count", segment_id=manifest.segment_id))
        if manifest.state == SegmentState.RETIRED and manifest.segment_id in shard_manifest.active_segment_ids:
            issues.append(ManifestValidationIssue(level="error", message="retired segment still active", segment_id=manifest.segment_id))

    for segment_id in shard_manifest.active_segment_ids:
        if segment_id not in by_segment_id:
            issues.append(ManifestValidationIssue(level="error", message="active segment missing manifest", segment_id=segment_id))

    return issues
