from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

from recalllayer.engine.mutable_buffer import MutableBufferEntry
from recalllayer.model.manifest import SegmentManifest, SegmentState
from recalllayer.quantization.base import EncodedVector, Quantizer
from recalllayer.retrieval.base import IndexedVector

SEGMENT_FORMAT_VERSION = "v1"
KNOWN_SEGMENT_FORMAT_VERSIONS = {"v1"}


@dataclass(slots=True)
class LocalSegmentPaths:
    segment_path: Path
    manifest_path: Path


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
    ) -> tuple[SegmentManifest, LocalSegmentPaths]:
        shard_dir = self.root_dir / collection_id / shard_id
        shard_dir.mkdir(parents=True, exist_ok=True)
        segment_path = shard_dir / f"{segment_id}.segment.jsonl"
        manifest_path = shard_dir / f"{segment_id}.manifest.json"

        row_count = 0
        min_write_epoch: int | None = None
        max_write_epoch: int | None = None

        with segment_path.open("w", encoding="utf-8") as handle:
            # Write a header row with format version
            header: dict[str, object] = {"__header__": True, "format_version": SEGMENT_FORMAT_VERSION}
            handle.write(json.dumps(header, separators=(",", ":")))
            handle.write("\n")
            for local_docno, entry in enumerate(entries):
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
                    min_write_epoch = epoch if min_write_epoch is None else min(min_write_epoch, epoch)
                    max_write_epoch = epoch if max_write_epoch is None else max(max_write_epoch, epoch)
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


class SegmentReader:
    """Reads local JSONL-backed sealed segments."""

    def __init__(self, segment_path: str | Path, *, cache=None) -> None:
        self.segment_path = Path(segment_path)
        self._cache = cache  # optional SegmentReadCache instance

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
        with self.segment_path.open("r", encoding="utf-8") as handle:
            for line in handle:
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
                yield IndexedVector(
                    vector_id=payload["vector_id"],
                    encoded=EncodedVector(
                        codes=np.asarray(payload["codes"], dtype=np.int8),
                        scale=float(payload["scale"]),
                    ),
                    metadata=payload.get("metadata", {}),
                )


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
