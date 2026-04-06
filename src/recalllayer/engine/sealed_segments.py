from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, Iterator

import numpy as np

from recalllayer.engine.mutable_buffer import MutableBufferEntry
from recalllayer.model.manifest import SegmentManifest, SegmentState
from recalllayer.quantization.base import EncodedVector, Quantizer
from recalllayer.retrieval.base import IndexedVector

SEGMENT_FORMAT_VERSION = "v1"
KNOWN_SEGMENT_FORMAT_VERSIONS = {"v1", "v2"}


@dataclass(slots=True)
class LocalSegmentPaths:
    segment_path: Path
    manifest_path: Path


@dataclass(slots=True)
class SegmentReadStats:
    file_reads: int = 0
    file_read_bytes: int = 0
    file_read_latency_ms: float = 0.0
    decode_loads: int = 0
    decoded_vector_count: int = 0
    decode_latency_ms: float = 0.0

    def snapshot(self) -> dict[str, float | int]:
        return {
            "file_reads": self.file_reads,
            "file_read_bytes": self.file_read_bytes,
            "file_read_latency_ms": self.file_read_latency_ms,
            "decode_loads": self.decode_loads,
            "decoded_vector_count": self.decoded_vector_count,
            "decode_latency_ms": self.decode_latency_ms,
        }

    def reset(self) -> None:
        self.file_reads = 0
        self.file_read_bytes = 0
        self.file_read_latency_ms = 0.0
        self.decode_loads = 0
        self.decoded_vector_count = 0
        self.decode_latency_ms = 0.0


class SegmentBuilder:
    """Builds a local JSONL-backed sealed segment from live mutable entries."""

    def __init__(self, root_dir: str | Path, *, quantizer: Quantizer) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.quantizer = quantizer

    def build(
        self,
        *,
        collection_id: str,
        shard_id: str,
        segment_id: str,
        generation: int,
        embedding_version: str,
        quantizer_version: str,
        entries: Iterable[MutableBufferEntry],
        n_ivf_clusters: int | None = None,
    ) -> tuple[SegmentManifest, LocalSegmentPaths]:
        entries_list = list(entries)
        if n_ivf_clusters is not None and n_ivf_clusters > 0:
            return self._build_clustered(
                collection_id=collection_id,
                shard_id=shard_id,
                segment_id=segment_id,
                generation=generation,
                embedding_version=embedding_version,
                quantizer_version=quantizer_version,
                entries=entries_list,
                n_ivf_clusters=n_ivf_clusters,
            )

        shard_dir = self.root_dir / collection_id / shard_id
        shard_dir.mkdir(parents=True, exist_ok=True)
        segment_path = shard_dir / f"{segment_id}.segment.jsonl"
        manifest_path = shard_dir / f"{segment_id}.manifest.json"

        row_count = 0
        min_write_epoch: int | None = None
        max_write_epoch: int | None = None

        with segment_path.open("w", encoding="utf-8") as handle:
            # Write a header row with format version
            header: dict[str, object] = {
                "__header__": True,
                "format_version": SEGMENT_FORMAT_VERSION,
            }
            handle.write(json.dumps(header, separators=(",", ":")))
            handle.write("\n")
            for local_docno, entry in enumerate(entries_list):
                epoch = entry.record.latest_write_epoch
                if entry.record.is_deleted:
                    # Write a tombstone marker so compactors can physically delete rows.
                    payload: dict[str, object] = {
                        "local_docno": local_docno,
                        "vector_id": entry.record.vector_id,
                        "is_deleted": True,
                        "write_epoch": epoch,
                    }
                    handle.write(json.dumps(payload, separators=(",", ":")))
                    handle.write("\n")
                    min_write_epoch = (
                        epoch if min_write_epoch is None else min(min_write_epoch, epoch)
                    )
                    max_write_epoch = (
                        epoch if max_write_epoch is None else max(max_write_epoch, epoch)
                    )
                    continue
                if entry.embedding is None:
                    continue
                encoded = self.quantizer.encode(entry.embedding)
                payload = {
                    "local_docno": local_docno,
                    "vector_id": entry.record.vector_id,
                    "codes": encoded.codes.tolist(),
                    "scale": encoded.scale,
                    "metadata": entry.metadata,
                    "write_epoch": epoch,
                }
                handle.write(json.dumps(payload, separators=(",", ":")))
                handle.write("\n")
                row_count += 1
                min_write_epoch = epoch if min_write_epoch is None else min(min_write_epoch, epoch)
                max_write_epoch = epoch if max_write_epoch is None else max(max_write_epoch, epoch)

        manifest = SegmentManifest(
            segment_id=segment_id,
            collection_id=collection_id,
            shard_id=shard_id,
            generation=generation,
            state=SegmentState.SEALED,
            row_count=row_count,
            live_row_count=row_count,
            deleted_row_count=0,
            embedding_version=embedding_version,
            quantizer_version=quantizer_version,
            min_write_epoch=min_write_epoch or 0,
            max_write_epoch=max_write_epoch or 0,
        )
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest, LocalSegmentPaths(segment_path=segment_path, manifest_path=manifest_path)

    def _build_clustered(
        self,
        *,
        collection_id: str,
        shard_id: str,
        segment_id: str,
        generation: int,
        embedding_version: str,
        quantizer_version: str,
        entries: list[MutableBufferEntry],
        n_ivf_clusters: int,
    ) -> tuple[SegmentManifest, LocalSegmentPaths]:
        """Write a v2 clustered segment: rows grouped by IVF cluster with a header index."""
        from recalllayer.engine.centroid_index import CentroidIndex

        shard_dir = self.root_dir / collection_id / shard_id
        shard_dir.mkdir(parents=True, exist_ok=True)
        segment_path = shard_dir / f"{segment_id}.segment.jsonl"
        manifest_path = shard_dir / f"{segment_id}.manifest.json"

        # Encode all live entries upfront so we can run k-means on them.
        live: list[tuple[MutableBufferEntry, np.ndarray, float]] = []  # (entry, codes, scale)
        for entry in entries:
            if entry.record.is_deleted or entry.embedding is None:
                continue
            encoded = self.quantizer.encode(entry.embedding)
            live.append((entry, encoded.codes, encoded.scale))

        # Build IVF index over decoded vectors.
        from recalllayer.retrieval.base import IndexedVector as _IV
        from recalllayer.quantization.base import EncodedVector as _EV
        ivs = [
            _IV(
                vector_id=e.record.vector_id,
                encoded=_EV(codes=codes, scale=scale),
                metadata=e.metadata,
            )
            for e, codes, scale in live
        ]
        k = min(n_ivf_clusters, len(ivs)) if ivs else 1
        ivf = CentroidIndex(n_clusters=k)
        ivf.build(ivs, quantizer=self.quantizer)

        # Invert bucket assignments: vector_id → cluster_id.
        assignments: dict[str, int] = {}
        for cluster_id, bucket in enumerate(ivf._buckets):
            for vid in bucket.vector_ids:
                assignments[vid] = cluster_id

        # Group live entries by cluster.
        clusters: dict[int, list[tuple[MutableBufferEntry, np.ndarray, float]]] = {}
        for e, codes, scale in live:
            cid = assignments.get(e.record.vector_id, 0)
            clusters.setdefault(cid, []).append((e, codes, scale))

        # Write all rows to a byte buffer, tracking per-cluster byte offsets.
        row_buf = io.BytesIO()
        cluster_index: dict[str, dict[str, int]] = {}
        min_write_epoch: int | None = None
        max_write_epoch: int | None = None
        row_count = 0
        local_docno = 0

        for cid in range(len(ivf._buckets)):
            cluster_entries = clusters.get(cid, [])
            if not cluster_entries:
                continue
            cluster_start = row_buf.tell()
            count = 0
            for entry, codes, scale in cluster_entries:
                epoch = entry.record.latest_write_epoch
                payload: dict[str, object] = {
                    "local_docno": local_docno,
                    "vector_id": entry.record.vector_id,
                    "cluster_id": cid,
                    "codes": codes.tolist(),
                    "scale": scale,
                    "metadata": entry.metadata,
                    "write_epoch": epoch,
                }
                row_buf.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
                local_docno += 1
                count += 1
                row_count += 1
                min_write_epoch = epoch if min_write_epoch is None else min(min_write_epoch, epoch)
                max_write_epoch = epoch if max_write_epoch is None else max(max_write_epoch, epoch)
            cluster_index[str(cid)] = {"byte_offset": cluster_start, "row_count": count}

        # Also write deleted entries (tombstones) grouped after live rows.
        tombstone_start = row_buf.tell()
        tombstone_count = 0
        for entry in entries:
            if not entry.record.is_deleted:
                continue
            epoch = entry.record.latest_write_epoch
            payload = {
                "local_docno": local_docno,
                "vector_id": entry.record.vector_id,
                "is_deleted": True,
                "write_epoch": epoch,
            }
            row_buf.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
            local_docno += 1
            tombstone_count += 1
            min_write_epoch = epoch if min_write_epoch is None else min(min_write_epoch, epoch)
            max_write_epoch = epoch if max_write_epoch is None else max(max_write_epoch, epoch)

        row_bytes = row_buf.getvalue()

        # Build the header with cluster centroids and placeholder byte offsets.
        centroids_list = [b.centroid.tolist() for b in ivf._buckets]
        bucket_vector_ids = {str(i): b.vector_ids for i, b in enumerate(ivf._buckets)}
        header: dict[str, object] = {
            "__header__": True,
            "format_version": "v2",
            "cluster_centroids": centroids_list,
            "bucket_vector_ids": bucket_vector_ids,
            "cluster_index": cluster_index,
        }
        header_line = (json.dumps(header, separators=(",", ":")) + "\n").encode("utf-8")
        header_size = len(header_line)

        # Adjust cluster byte offsets to account for the header line.
        for v in cluster_index.values():
            v["byte_offset"] += header_size
        header["cluster_index"] = cluster_index
        header_line = (json.dumps(header, separators=(",", ":")) + "\n").encode("utf-8")
        # If the header grew (digit-count change in offsets), do one more adjustment.
        new_header_size = len(header_line)
        if new_header_size != header_size:
            diff = new_header_size - header_size
            for v in cluster_index.values():
                v["byte_offset"] += diff
            header["cluster_index"] = cluster_index
            header_line = (json.dumps(header, separators=(",", ":")) + "\n").encode("utf-8")

        with segment_path.open("wb") as handle:
            handle.write(header_line)
            handle.write(row_bytes)

        manifest = SegmentManifest(
            segment_id=segment_id,
            collection_id=collection_id,
            shard_id=shard_id,
            generation=generation,
            state=SegmentState.SEALED,
            row_count=row_count,
            live_row_count=row_count,
            deleted_row_count=0,
            embedding_version=embedding_version,
            quantizer_version=quantizer_version,
            min_write_epoch=min_write_epoch or 0,
            max_write_epoch=max_write_epoch or 0,
        )
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest, LocalSegmentPaths(segment_path=segment_path, manifest_path=manifest_path)


class SegmentReader:
    """Reads local JSONL-backed sealed segments."""

    def __init__(
        self, segment_path: str | Path, *, cache=None, read_stats: SegmentReadStats | None = None
    ) -> None:
        self.segment_path = Path(segment_path)
        self._cache = cache  # optional SegmentReadCache instance
        self._read_stats = read_stats

    def read_format_version(self) -> str | None:
        """Return the format_version from the segment header, or None if absent."""
        with self.segment_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline().strip()
            if not first_line:
                return None
            payload = json.loads(first_line)
            if payload.get("__header__"):
                return payload.get("format_version")
        return None

    def read_v2_header(self) -> dict | None:
        """Return v2 cluster header data, or None if the segment is not v2.

        Returns a dict with keys: ``cluster_centroids``, ``bucket_vector_ids``,
        ``cluster_index`` (maps str(cluster_id) → {byte_offset, row_count}).
        """
        with self.segment_path.open("rb") as handle:
            first_line = handle.readline()
        if not first_line:
            return None
        try:
            payload = json.loads(first_line)
        except json.JSONDecodeError:
            return None
        if not payload.get("__header__") or payload.get("format_version") != "v2":
            return None
        return payload

    def iter_cluster_vectors(self, cluster_ids: set[int]) -> Iterator[IndexedVector]:
        """Read only vectors from the specified clusters (v2 segments).

        Falls back to ``iter_indexed_vectors`` for v1 segments.
        """
        header = self.read_v2_header()
        if header is None:
            yield from self.iter_indexed_vectors()
            return

        cluster_index: dict[str, dict] = header.get("cluster_index", {})
        with self.segment_path.open("rb") as handle:
            for cluster_id in sorted(cluster_ids):
                cluster_data = cluster_index.get(str(cluster_id))
                if cluster_data is None:
                    continue
                handle.seek(cluster_data["byte_offset"])
                for _ in range(cluster_data["row_count"]):
                    raw = handle.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8").strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    if payload.get("is_deleted"):
                        continue
                    yield IndexedVector(
                        vector_id=payload["vector_id"],
                        encoded=EncodedVector(
                            codes=np.asarray(payload["codes"], dtype=np.int8),
                            scale=float(payload["scale"]),
                        ),
                        metadata=payload.get("metadata", {}),
                    )

    def iter_indexed_vectors(self) -> Iterator[IndexedVector]:
        if self._cache is not None:
            cached = self._cache.get(self.segment_path)
            if cached is not None:
                yield from cached
                return
        vectors = list(self._read_indexed_vectors())
        if self._cache is not None:
            self._cache.put(self.segment_path, vectors)
        yield from vectors

    def _read_indexed_vectors(self) -> Iterator[IndexedVector]:
        read_start = perf_counter()
        with self.segment_path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        read_latency_ms = (perf_counter() - read_start) * 1000.0
        if self._read_stats is not None:
            self._read_stats.file_reads += 1
            self._read_stats.file_read_bytes += self.segment_path.stat().st_size
            self._read_stats.file_read_latency_ms += read_latency_ms

        decode_start = perf_counter()
        decoded_count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            # First line may be a header; validate version and skip it.
            if payload.get("__header__"):
                version = payload.get("format_version")
                if version not in KNOWN_SEGMENT_FORMAT_VERSIONS:
                    raise ValueError(
                        f"Unknown segment format version {version!r} in {self.segment_path}. "
                        f"Known versions: {sorted(KNOWN_SEGMENT_FORMAT_VERSIONS)}"
                    )
                continue
            # Skip tombstone rows
            if payload.get("is_deleted"):
                continue
            decoded_count += 1
            yield IndexedVector(
                vector_id=payload["vector_id"],
                encoded=EncodedVector(
                    codes=np.asarray(payload["codes"], dtype=np.int8),
                    scale=float(payload["scale"]),
                ),
                metadata=payload.get("metadata", {}),
            )
        if self._read_stats is not None:
            self._read_stats.decode_loads += 1
            self._read_stats.decoded_vector_count += decoded_count
            self._read_stats.decode_latency_ms += (perf_counter() - decode_start) * 1000.0


class LocalSegmentStore:
    """Tiny helper for listing and loading locally sealed segments."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def list_segment_files(self, *, collection_id: str, shard_id: str) -> list[Path]:
        shard_dir = self.root_dir / collection_id / shard_id
        if not shard_dir.exists():
            return []
        return sorted(shard_dir.glob("*.segment.jsonl"))
