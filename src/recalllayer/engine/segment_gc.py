from dataclasses import dataclass
from pathlib import Path

from recalllayer.model.manifest import SegmentManifest, SegmentState


@dataclass(slots=True)
class SegmentGarbageCandidate:
    segment_id: str
    segment_path: Path
    manifest_paths: list[Path]


@dataclass(slots=True)
class SegmentGarbageCollectionResult:
    removed_segment_ids: list[str]
    removed_paths: list[Path]


def plan_segment_garbage_collection(
    *,
    manifests: list[SegmentManifest],
    segments_root: str | Path,
    manifests_root: str | Path | None = None,
) -> list[SegmentGarbageCandidate]:
    root = Path(segments_root)
    manifest_root = Path(manifests_root) if manifests_root is not None else None
    candidates: list[SegmentGarbageCandidate] = []
    for manifest in manifests:
        if manifest.state != SegmentState.RETIRED:
            continue
        shard_dir = root / manifest.collection_id / manifest.shard_id
        manifest_paths = [shard_dir / f"{manifest.segment_id}.manifest.json"]
        if manifest_root is not None:
            extra_manifest_path = manifest_root / manifest.collection_id / manifest.shard_id / f"{manifest.segment_id}.manifest.json"
            if extra_manifest_path not in manifest_paths:
                manifest_paths.append(extra_manifest_path)
        candidates.append(
            SegmentGarbageCandidate(
                segment_id=manifest.segment_id,
                segment_path=shard_dir / f"{manifest.segment_id}.segment.jsonl",
                manifest_paths=manifest_paths,
            )
        )
    return candidates


def execute_segment_garbage_collection(candidates: list[SegmentGarbageCandidate]) -> SegmentGarbageCollectionResult:
    removed_segment_ids: list[str] = []
    removed_paths: list[Path] = []
    for candidate in candidates:
        for path in [candidate.segment_path, *candidate.manifest_paths]:
            if path.exists():
                path.unlink()
                removed_paths.append(path)
        removed_segment_ids.append(candidate.segment_id)
    return SegmentGarbageCollectionResult(removed_segment_ids=removed_segment_ids, removed_paths=removed_paths)
