from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from recalllayer.engine.sealed_segments import LocalSegmentStore
from recalllayer.model.manifest import SegmentManifest, SegmentState, ShardManifest
from recalllayer.quantization.base import Quantizer


@dataclass(slots=True)
class CompactionArtifacts:
    segment_manifest: SegmentManifest
    shard_manifest: ShardManifest
    source_segment_ids: list[str]
    segment_path: Path
    manifest_path: Path


class LocalSegmentCompactor:
    """Merge multiple local sealed segments into one latest-write-wins segment."""

    def __init__(
        self,
        *,
        segments_root: str | Path,
        manifests_root: str | Path,
        quantizer: Quantizer | None = None,
    ) -> None:
        self.segment_store = LocalSegmentStore(segments_root)
        self.segments_root = Path(segments_root)
        self.manifests_root = Path(manifests_root)
        self.manifests_root.mkdir(parents=True, exist_ok=True)
        self.quantizer = quantizer

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
        n_ivf_clusters: int | None = None,
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
                    if payload.get('__header__'):
                        continue
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

        if self.quantizer is not None and n_ivf_clusters is not None and n_ivf_clusters > 0:
            self._write_v2(segment_path, live_rows, n_ivf_clusters=n_ivf_clusters)
        else:
            self._write_v1(segment_path, live_rows)

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

    def _write_v1(self, segment_path: Path, live_rows: dict[str, dict]) -> None:
        """Write a v1-format segment: header line followed by rows in sorted order."""
        with segment_path.open("w", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"__header__": True, "format_version": "v1"}, separators=(",", ":"))
                + "\n"
            )
            for local_docno, vector_id in enumerate(sorted(live_rows)):
                payload = dict(live_rows[vector_id])
                payload["local_docno"] = local_docno
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

    def _write_v2(
        self, segment_path: Path, live_rows: dict[str, dict], *, n_ivf_clusters: int
    ) -> None:
        """Write a v2 clustered segment: k-means on the live codes, rows grouped by cluster."""
        from recalllayer.engine.centroid_index import CentroidIndex
        from recalllayer.quantization.base import EncodedVector
        from recalllayer.retrieval.base import IndexedVector

        assert self.quantizer is not None

        ivs = [
            IndexedVector(
                vector_id=vid,
                encoded=EncodedVector(
                    codes=np.asarray(row["codes"], dtype=np.int8),
                    scale=float(row["scale"]),
                ),
                metadata=row.get("metadata", {}),
            )
            for vid, row in live_rows.items()
            if "codes" in row and "scale" in row
        ]

        k = min(n_ivf_clusters, len(ivs)) if ivs else 1
        ivf = CentroidIndex(n_clusters=k)
        ivf.build(ivs, quantizer=self.quantizer)

        assignments: dict[str, int] = {}
        for cid, bucket in enumerate(ivf._buckets):
            for vid in bucket.vector_ids:
                assignments[vid] = cid

        clusters: dict[int, list[str]] = {}
        for vid in live_rows:
            cid = assignments.get(vid, 0)
            clusters.setdefault(cid, []).append(vid)

        row_buf = io.BytesIO()
        cluster_index: dict[str, dict[str, int]] = {}
        local_docno = 0

        for cid in range(len(ivf._buckets)):
            vids = clusters.get(cid, [])
            if not vids:
                continue
            cluster_start = row_buf.tell()
            count = 0
            for vid in vids:
                payload = dict(live_rows[vid])
                payload["local_docno"] = local_docno
                payload["cluster_id"] = cid
                row_buf.write(
                    (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
                )
                local_docno += 1
                count += 1
            cluster_index[str(cid)] = {"byte_offset": cluster_start, "row_count": count}

        row_bytes = row_buf.getvalue()

        centroids_list = [b.centroid.tolist() for b in ivf._buckets]
        bucket_vector_ids = {str(i): b.vector_ids for i, b in enumerate(ivf._buckets)}
        header: dict = {
            "__header__": True,
            "format_version": "v2",
            "cluster_centroids": centroids_list,
            "bucket_vector_ids": bucket_vector_ids,
            "cluster_index": cluster_index,
        }
        header_line = (json.dumps(header, separators=(",", ":")) + "\n").encode("utf-8")
        header_size = len(header_line)

        for v in cluster_index.values():
            v["byte_offset"] += header_size
        header["cluster_index"] = cluster_index
        header_line = (json.dumps(header, separators=(",", ":")) + "\n").encode("utf-8")
        new_size = len(header_line)
        if new_size != header_size:
            diff = new_size - header_size
            for v in cluster_index.values():
                v["byte_offset"] += diff
            header["cluster_index"] = cluster_index
            header_line = (json.dumps(header, separators=(",", ":")) + "\n").encode("utf-8")

        with segment_path.open("wb") as handle:
            handle.write(header_line)
            handle.write(row_bytes)
