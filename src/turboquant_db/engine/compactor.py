from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from turboquant_db.engine.sealed_segments import LocalSegmentStore
from turboquant_db.model.manifest import SegmentManifest, SegmentState, ShardManifest


@dataclass(slots=True)
class CompactionArtifacts:
    segment_manifest: SegmentManifest
    shard_manifest: ShardManifest
    source_segment_ids: list[str]
    segment_path: Path
    manifest_path: Path


class LocalSegmentCompactor:
    """Merge multiple local sealed segments into one latest-write-wins segment."""

    def __init__(self, *, segments_root: str | Path, manifests_root: str | Path) -> None:
        self.segment_store = LocalSegmentStore(segments_root)
        self.segments_root = Path(segments_root)
        self.manifests_root = Path(manifests_root)
        self.manifests_root.mkdir(parents=True, exist_ok=True)

    def compact(
        self,
        *,
        collection_id: str,
        shard_id: str = "shard-0",
        output_segment_id: str = "seg-compacted",
        generation: int = 1,
        embedding_version: str = "embed-v1",
        quantizer_version: str = "tq-v0",
        source_segment_ids: list[str] | None = None,
    ) -> CompactionArtifacts:
        available_paths = self.segment_store.list_segment_files(collection_id=collection_id, shard_id=shard_id)
        if source_segment_ids is None:
            source_paths = available_paths
        else:
            requested = set(source_segment_ids)
            source_paths = [path for path in available_paths if path.name.replace('.segment.jsonl', '') in requested]
        if not source_paths:
            raise ValueError("no sealed segments available for compaction")

        # latest_rows: vector_id -> row payload (may be a tombstone)
        latest_rows: dict[str, dict[str, object]] = {}
        min_write_epoch: int | None = None
        max_write_epoch: int | None = None
        source_ids: list[str] = []

        for path in source_paths:
            segment_id = path.name.replace('.segment.jsonl', '')
            source_ids.append(segment_id)
            with path.open('r', encoding='utf-8') as handle:
                for line in handle:
                    payload = json.loads(line)
                    vector_id = payload['vector_id']
                    write_epoch = int(payload.get('write_epoch', 0))
                    current = latest_rows.get(vector_id)
                    if current is None or int(current.get('write_epoch', 0)) < write_epoch:
                        latest_rows[vector_id] = payload
                    min_write_epoch = write_epoch if min_write_epoch is None else min(min_write_epoch, write_epoch)
                    max_write_epoch = write_epoch if max_write_epoch is None else max(max_write_epoch, write_epoch)

        # Physical delete: remove tombstoned and superseded rows
        live_rows = {
            vid: row
            for vid, row in latest_rows.items()
            if not row.get('is_deleted', False)
        }

        shard_dir = self.segments_root / collection_id / shard_id
        shard_dir.mkdir(parents=True, exist_ok=True)
        segment_path = shard_dir / f"{output_segment_id}.segment.jsonl"
        manifest_dir = self.manifests_root / collection_id / shard_id
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"{output_segment_id}.manifest.json"

        with segment_path.open('w', encoding='utf-8') as handle:
            for local_docno, vector_id in enumerate(sorted(live_rows)):
                payload = dict(live_rows[vector_id])
                payload['local_docno'] = local_docno
                handle.write(json.dumps(payload, separators=(",", ":")))
                handle.write("\n")

        segment_manifest = SegmentManifest(
            segment_id=output_segment_id,
            collection_id=collection_id,
            shard_id=shard_id,
            generation=generation,
            state=SegmentState.SEALED,
            row_count=len(live_rows),
            live_row_count=len(live_rows),
            deleted_row_count=0,
            embedding_version=embedding_version,
            quantizer_version=quantizer_version,
            min_write_epoch=min_write_epoch or 0,
            max_write_epoch=max_write_epoch or 0,
        )
        manifest_path.write_text(segment_manifest.model_dump_json(indent=2), encoding='utf-8')

        shard_manifest = ShardManifest(
            shard_id=shard_id,
            collection_id=collection_id,
            active_segment_ids=[output_segment_id],
        )

        return CompactionArtifacts(
            segment_manifest=segment_manifest,
            shard_manifest=shard_manifest,
            source_segment_ids=source_ids,
            segment_path=segment_path,
            manifest_path=manifest_path,
        )
