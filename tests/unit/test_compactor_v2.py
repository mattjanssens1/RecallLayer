"""Tests for LocalSegmentCompactor v1/v2 format handling.

Verifies:
- Compacted output always has a format_version header (no more headerless segments)
- With quantizer + n_ivf_clusters, compaction preserves v2 clustered layout
- v2 compacted segments support IVF-accelerated queries end-to-end
- Compacting v2 sources without quantizer gracefully downgrades to v1
- CompactionExecutor threads n_ivf_clusters through to the compactor
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from recalllayer.engine.compaction_executor import CompactionExecutor
from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.manifest_store import ManifestStore
from recalllayer.engine.sealed_segments import SegmentBuilder, SegmentReader
from recalllayer.engine.segment_manifest_store import SegmentManifestStore
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.model.manifest import SegmentState
from recalllayer.quantization.scalar import ScalarQuantizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_v1_segment(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"__header__": True, "format_version": "v1"}, separators=(",", ":")) + "\n")
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def _write_headerless_segment(path: Path, rows: list[dict]) -> None:
    """Legacy format — no header line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def _make_v2_segment(tmp_path: Path, items: list[tuple[str, list[float]]], shard_dir: Path) -> Path:
    """Build a v2 segment directly via SegmentBuilder and place it in shard_dir."""
    from recalllayer.engine.mutable_buffer import MutableBuffer
    buf = MutableBuffer(collection_id="col")
    for i, (vid, emb) in enumerate(items, start=1):
        buf.upsert(
            vector_id=vid,
            embedding=emb,
            metadata={"idx": i},
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
            write_epoch=i,
        )
    builder = SegmentBuilder(shard_dir.parent.parent, quantizer=ScalarQuantizer())
    _, paths = builder.build(
        collection_id="col",
        shard_id="shard-0",
        segment_id="seg-src",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        entries=buf.live_entries(),
        n_ivf_clusters=2,
    )
    return paths.segment_path


# ---------------------------------------------------------------------------
# v1 header always written
# ---------------------------------------------------------------------------

def test_compacted_v1_source_has_format_version_header(tmp_path: Path) -> None:
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [{"local_docno": 0, "vector_id": "a", "codes": [1, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1}],
    )
    compactor = LocalSegmentCompactor(segments_root=tmp_path / "segments", manifests_root=tmp_path / "manifests")
    artifacts = compactor.compact(collection_id="col", output_segment_id="seg-out", generation=2)
    assert SegmentReader(artifacts.segment_path).read_format_version() == "v1"


def test_compacted_headerless_source_has_format_version_header(tmp_path: Path) -> None:
    """Even if source was a legacy headerless segment, compacted output gets a header."""
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_headerless_segment(
        shard_dir / "seg-1.segment.jsonl",
        [{"local_docno": 0, "vector_id": "a", "codes": [1, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1}],
    )
    compactor = LocalSegmentCompactor(segments_root=tmp_path / "segments", manifests_root=tmp_path / "manifests")
    artifacts = compactor.compact(collection_id="col", output_segment_id="seg-out", generation=2)
    version = SegmentReader(artifacts.segment_path).read_format_version()
    assert version == "v1"


def test_compacted_output_rows_are_readable_after_v1_header_added(tmp_path: Path) -> None:
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [1, 0], "scale": 1.0, "metadata": {"tag": "x"}, "write_epoch": 1},
            {"local_docno": 1, "vector_id": "b", "codes": [0, 1], "scale": 1.0, "metadata": {"tag": "y"}, "write_epoch": 2},
        ],
    )
    compactor = LocalSegmentCompactor(segments_root=tmp_path / "segments", manifests_root=tmp_path / "manifests")
    artifacts = compactor.compact(collection_id="col", output_segment_id="seg-out", generation=2)
    rows = list(SegmentReader(artifacts.segment_path).iter_indexed_vectors())
    assert {r.vector_id for r in rows} == {"a", "b"}


# ---------------------------------------------------------------------------
# v2 output when quantizer + n_ivf_clusters provided
# ---------------------------------------------------------------------------

def test_compaction_writes_v2_when_quantizer_and_n_ivf_clusters_provided(tmp_path: Path) -> None:
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [127, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1},
            {"local_docno": 1, "vector_id": "b", "codes": [0, 127], "scale": 1.0, "metadata": {}, "write_epoch": 2},
            {"local_docno": 2, "vector_id": "c", "codes": [100, 0], "scale": 1.0, "metadata": {}, "write_epoch": 3},
            {"local_docno": 3, "vector_id": "d", "codes": [0, 100], "scale": 1.0, "metadata": {}, "write_epoch": 4},
        ],
    )
    compactor = LocalSegmentCompactor(
        segments_root=tmp_path / "segments",
        manifests_root=tmp_path / "manifests",
        quantizer=ScalarQuantizer(),
    )
    artifacts = compactor.compact(
        collection_id="col", output_segment_id="seg-out", generation=2, n_ivf_clusters=2
    )
    assert SegmentReader(artifacts.segment_path).read_format_version() == "v2"


def test_compaction_v2_header_has_cluster_index(tmp_path: Path) -> None:
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [127, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1},
            {"local_docno": 1, "vector_id": "b", "codes": [0, 127], "scale": 1.0, "metadata": {}, "write_epoch": 2},
            {"local_docno": 2, "vector_id": "c", "codes": [110, 0], "scale": 1.0, "metadata": {}, "write_epoch": 3},
            {"local_docno": 3, "vector_id": "d", "codes": [0, 110], "scale": 1.0, "metadata": {}, "write_epoch": 4},
        ],
    )
    compactor = LocalSegmentCompactor(
        segments_root=tmp_path / "segments",
        manifests_root=tmp_path / "manifests",
        quantizer=ScalarQuantizer(),
    )
    artifacts = compactor.compact(
        collection_id="col", output_segment_id="seg-out", generation=2, n_ivf_clusters=2
    )
    header = SegmentReader(artifacts.segment_path).read_v2_header()
    assert header is not None
    assert "cluster_centroids" in header
    assert "cluster_index" in header
    assert len(header["cluster_centroids"]) == 2


def test_compaction_v2_all_vectors_readable(tmp_path: Path) -> None:
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [127, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1},
            {"local_docno": 1, "vector_id": "b", "codes": [0, 127], "scale": 1.0, "metadata": {}, "write_epoch": 2},
        ],
    )
    compactor = LocalSegmentCompactor(
        segments_root=tmp_path / "segments",
        manifests_root=tmp_path / "manifests",
        quantizer=ScalarQuantizer(),
    )
    artifacts = compactor.compact(
        collection_id="col", output_segment_id="seg-out", generation=2, n_ivf_clusters=2
    )
    rows = list(SegmentReader(artifacts.segment_path).iter_indexed_vectors())
    assert {r.vector_id for r in rows} == {"a", "b"}


def test_compaction_merges_two_v2_sources_into_v2(tmp_path: Path) -> None:
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [{"local_docno": 0, "vector_id": "a", "codes": [127, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1}],
    )
    _write_v1_segment(
        shard_dir / "seg-2.segment.jsonl",
        [{"local_docno": 0, "vector_id": "b", "codes": [0, 127], "scale": 1.0, "metadata": {}, "write_epoch": 2}],
    )
    compactor = LocalSegmentCompactor(
        segments_root=tmp_path / "segments",
        manifests_root=tmp_path / "manifests",
        quantizer=ScalarQuantizer(),
    )
    artifacts = compactor.compact(
        collection_id="col", output_segment_id="seg-out", generation=3, n_ivf_clusters=2
    )
    assert SegmentReader(artifacts.segment_path).read_format_version() == "v2"
    rows = list(SegmentReader(artifacts.segment_path).iter_indexed_vectors())
    assert {r.vector_id for r in rows} == {"a", "b"}


def test_compaction_v2_tombstones_excluded(tmp_path: Path) -> None:
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [127, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1},
            {"local_docno": 1, "vector_id": "b", "codes": [0, 127], "scale": 1.0, "metadata": {}, "write_epoch": 2},
        ],
    )
    _write_v1_segment(
        shard_dir / "seg-2.segment.jsonl",
        [{"local_docno": 0, "vector_id": "a", "is_deleted": True, "write_epoch": 3}],
    )
    compactor = LocalSegmentCompactor(
        segments_root=tmp_path / "segments",
        manifests_root=tmp_path / "manifests",
        quantizer=ScalarQuantizer(),
    )
    artifacts = compactor.compact(
        collection_id="col", output_segment_id="seg-out", generation=3, n_ivf_clusters=2
    )
    rows = list(SegmentReader(artifacts.segment_path).iter_indexed_vectors())
    assert {r.vector_id for r in rows} == {"b"}


# ---------------------------------------------------------------------------
# Graceful downgrade: v2 sources without quantizer → v1 output
# ---------------------------------------------------------------------------

def test_compaction_without_quantizer_writes_v1_from_v2_source(tmp_path: Path) -> None:
    """Compacting v2 segments without a quantizer degrades to v1 — data is preserved,
    IVF is lost, but the segment is correctly formatted and readable."""
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _make_v2_segment(
        tmp_path,
        [("a", [1.0, 0.0]), ("b", [0.0, 1.0])],
        shard_dir,
    )
    compactor = LocalSegmentCompactor(
        segments_root=tmp_path / "segments",
        manifests_root=tmp_path / "manifests",
        # no quantizer
    )
    artifacts = compactor.compact(collection_id="col", output_segment_id="seg-out", generation=2)
    assert SegmentReader(artifacts.segment_path).read_format_version() == "v1"
    rows = list(SegmentReader(artifacts.segment_path).iter_indexed_vectors())
    assert {r.vector_id for r in rows} == {"a", "b"}


# ---------------------------------------------------------------------------
# End-to-end: IVF-accelerated query on v2 compacted segment
# ---------------------------------------------------------------------------

def test_ivf_query_works_on_v2_compacted_segment(tmp_path: Path) -> None:
    """After compaction into a v2 segment, ShowcaseScoredDatabase should use IVF."""
    shard_dir = tmp_path / "segments" / "col" / "shard-0"
    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [127, 0], "scale": 1.0, "metadata": {"tag": "x"}, "write_epoch": 1},
            {"local_docno": 1, "vector_id": "b", "codes": [0, 127], "scale": 1.0, "metadata": {"tag": "y"}, "write_epoch": 2},
            {"local_docno": 2, "vector_id": "c", "codes": [100, 0], "scale": 1.0, "metadata": {"tag": "x"}, "write_epoch": 3},
        ],
    )
    compactor = LocalSegmentCompactor(
        segments_root=tmp_path / "segments",
        manifests_root=tmp_path / "manifests",
        quantizer=ScalarQuantizer(),
    )
    artifacts = compactor.compact(
        collection_id="col", output_segment_id="seg-compacted", generation=2, n_ivf_clusters=2
    )
    assert SegmentReader(artifacts.segment_path).read_format_version() == "v2"

    # Rebuild a ShowcaseScoredDatabase pointing at the compacted segment
    db = ShowcaseScoredDatabase(
        collection_id="col",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,
        enable_segment_cache=True,
    )
    # Register the compacted segment in the manifest
    from recalllayer.engine.manifest_store import ManifestStore
    from recalllayer.model.manifest import ShardManifest
    ManifestStore(tmp_path / "manifests").save(
        ShardManifest(
            shard_id="shard-0",
            collection_id="col",
            active_segment_ids=["seg-compacted"],
            replay_from_write_epoch=3,
        )
    )

    hits = db.query_compressed_hybrid_hits([1.0, 0.0], top_k=2)
    assert hits
    assert hits[0].vector_id == "a"
    # IVF index should have been reconstructed from the v2 header
    assert len(db._segment_ivf_indexes) == 1


# ---------------------------------------------------------------------------
# CompactionExecutor threads n_ivf_clusters through
# ---------------------------------------------------------------------------

def test_compaction_executor_passes_n_ivf_clusters(tmp_path: Path) -> None:
    from recalllayer.engine.segment_manifest_store import SegmentManifestStore
    from recalllayer.model.manifest import SegmentManifest, SegmentState, ShardManifest
    from datetime import datetime, timezone

    segments_root = tmp_path / "segments"
    manifests_root = tmp_path / "manifests"
    shard_dir = segments_root / "col" / "shard-0"

    _write_v1_segment(
        shard_dir / "seg-1.segment.jsonl",
        [{"local_docno": 0, "vector_id": "a", "codes": [127, 0], "scale": 1.0, "metadata": {}, "write_epoch": 1}],
    )
    _write_v1_segment(
        shard_dir / "seg-2.segment.jsonl",
        [{"local_docno": 0, "vector_id": "b", "codes": [0, 127], "scale": 1.0, "metadata": {}, "write_epoch": 2}],
    )

    now = datetime.now(timezone.utc)
    seg_manifest_store = SegmentManifestStore(manifests_root)
    for seg_id, epoch in [("seg-1", 1), ("seg-2", 2)]:
        seg_manifest_store.save(SegmentManifest(
            segment_id=seg_id,
            collection_id="col",
            shard_id="shard-0",
            generation=epoch,
            state=SegmentState.ACTIVE,
            row_count=1,
            live_row_count=1,
            deleted_row_count=0,
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
            min_write_epoch=epoch,
            max_write_epoch=epoch,
            sealed_at=now,
            activated_at=now,
        ))
    manifest_store = ManifestStore(manifests_root)
    manifest_store.save(ShardManifest(
        shard_id="shard-0",
        collection_id="col",
        active_segment_ids=["seg-1", "seg-2"],
        replay_from_write_epoch=2,
    ))

    executor = CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=100),
        compactor=LocalSegmentCompactor(
            segments_root=segments_root,
            manifests_root=manifests_root,
            quantizer=ScalarQuantizer(),
        ),
        manifest_store=manifest_store,
        segment_manifest_store=seg_manifest_store,
    )
    result = executor.compact_shard(
        collection_id="col",
        output_segment_id="seg-merged",
        generation=3,
        n_ivf_clusters=2,
    )
    assert result is not None
    assert SegmentReader(result.artifacts.segment_path).read_format_version() == "v2"
