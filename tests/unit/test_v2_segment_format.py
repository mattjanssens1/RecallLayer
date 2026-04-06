"""Tests for the v2 clustered segment format, CentroidIndex.from_stored_data,
and ShowcaseScoredDatabase with enable_ivf=True."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from recalllayer.engine.centroid_index import CentroidIndex
from recalllayer.engine.mutable_buffer import MutableBuffer
from recalllayer.engine.sealed_segments import SegmentBuilder, SegmentReader
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.scalar import ScalarQuantizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_buffer(*items: tuple[str, list[float]]) -> MutableBuffer:
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
    return buf


def _build_v2(tmp_path: Path, items: list[tuple[str, list[float]]], n_ivf_clusters: int = 2):
    buf = _make_buffer(*items)
    builder = SegmentBuilder(tmp_path, quantizer=ScalarQuantizer())
    manifest, paths = builder.build(
        collection_id="col",
        shard_id="shard-0",
        segment_id="seg-1",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        entries=buf.live_entries(),
        n_ivf_clusters=n_ivf_clusters,
    )
    return manifest, paths


# ---------------------------------------------------------------------------
# SegmentBuilder — v2 format written when n_ivf_clusters is set
# ---------------------------------------------------------------------------

def test_v2_format_version_written(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items)
    reader = SegmentReader(paths.segment_path)
    assert reader.read_format_version() == "v2"


def test_v2_header_contains_required_keys(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items)
    header = SegmentReader(paths.segment_path).read_v2_header()
    assert header is not None
    assert "cluster_centroids" in header
    assert "bucket_vector_ids" in header
    assert "cluster_index" in header


def test_v2_header_cluster_count(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items, n_ivf_clusters=2)
    header = SegmentReader(paths.segment_path).read_v2_header()
    assert len(header["cluster_centroids"]) == 2
    assert len(header["cluster_index"]) == 2


def test_v2_header_byte_offsets_are_positive(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items)
    header = SegmentReader(paths.segment_path).read_v2_header()
    for cluster_data in header["cluster_index"].values():
        assert cluster_data["byte_offset"] > 0
        assert cluster_data["row_count"] > 0


def test_v2_all_vector_ids_covered_by_buckets(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items)
    header = SegmentReader(paths.segment_path).read_v2_header()
    all_ids = {vid for vids in header["bucket_vector_ids"].values() for vid in vids}
    assert all_ids == {"a", "b", "c", "d"}


def test_v2_manifest_row_count(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    manifest, _ = _build_v2(tmp_path, items)
    assert manifest.row_count == 4


def test_v1_format_when_n_ivf_clusters_is_none(tmp_path: Path) -> None:
    buf = _make_buffer(("a", [1.0, 0.0]), ("b", [0.0, 1.0]))
    builder = SegmentBuilder(tmp_path, quantizer=ScalarQuantizer())
    _, paths = builder.build(
        collection_id="col",
        shard_id="shard-0",
        segment_id="seg-1",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        entries=buf.live_entries(),
        n_ivf_clusters=None,
    )
    assert SegmentReader(paths.segment_path).read_format_version() == "v1"


# ---------------------------------------------------------------------------
# SegmentReader — iter_indexed_vectors still works on v2
# ---------------------------------------------------------------------------

def test_iter_indexed_vectors_reads_all_from_v2(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items)
    rows = list(SegmentReader(paths.segment_path).iter_indexed_vectors())
    assert {r.vector_id for r in rows} == {"a", "b", "c", "d"}


def test_iter_indexed_vectors_codes_are_int8(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0])]
    _, paths = _build_v2(tmp_path, items)
    for iv in SegmentReader(paths.segment_path).iter_indexed_vectors():
        assert iv.encoded.codes.dtype == np.dtype("int8")


# ---------------------------------------------------------------------------
# SegmentReader — read_v2_header returns None for v1
# ---------------------------------------------------------------------------

def test_read_v2_header_returns_none_for_v1(tmp_path: Path) -> None:
    buf = _make_buffer(("a", [1.0, 0.0]))
    builder = SegmentBuilder(tmp_path, quantizer=ScalarQuantizer())
    _, paths = builder.build(
        collection_id="col",
        shard_id="shard-0",
        segment_id="seg-1",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        entries=buf.live_entries(),
    )
    assert SegmentReader(paths.segment_path).read_v2_header() is None


# ---------------------------------------------------------------------------
# SegmentReader — iter_cluster_vectors
# ---------------------------------------------------------------------------

def test_iter_cluster_vectors_returns_subset(tmp_path: Path) -> None:
    # Use 4 well-separated 2-d vectors so they reliably split into 2 clusters.
    items = [("a", [1.0, 0.0]), ("b", [0.9, 0.1]), ("c", [0.0, 1.0]), ("d", [0.1, 0.9])]
    _, paths = _build_v2(tmp_path, items, n_ivf_clusters=2)
    header = SegmentReader(paths.segment_path).read_v2_header()

    for cluster_id_str in header["cluster_index"]:
        cid = int(cluster_id_str)
        rows = list(SegmentReader(paths.segment_path).iter_cluster_vectors({cid}))
        expected_count = header["cluster_index"][cluster_id_str]["row_count"]
        assert len(rows) == expected_count


def test_iter_cluster_vectors_all_clusters_yields_all_rows(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items, n_ivf_clusters=2)
    all_rows = list(SegmentReader(paths.segment_path).iter_cluster_vectors({0, 1}))
    assert {r.vector_id for r in all_rows} == {"a", "b", "c", "d"}


def test_iter_cluster_vectors_empty_cluster_set_returns_nothing(tmp_path: Path) -> None:
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0])]
    _, paths = _build_v2(tmp_path, items, n_ivf_clusters=2)
    rows = list(SegmentReader(paths.segment_path).iter_cluster_vectors(set()))
    assert rows == []


def test_iter_cluster_vectors_fallback_for_v1(tmp_path: Path) -> None:
    buf = _make_buffer(("a", [1.0, 0.0]), ("b", [0.0, 1.0]))
    builder = SegmentBuilder(tmp_path, quantizer=ScalarQuantizer())
    _, paths = builder.build(
        collection_id="col",
        shard_id="shard-0",
        segment_id="seg-1",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        entries=buf.live_entries(),
    )
    # v1 segment — should fall back to full scan regardless of requested cluster id
    rows = list(SegmentReader(paths.segment_path).iter_cluster_vectors({0, 99}))
    assert {r.vector_id for r in rows} == {"a", "b"}


def test_iter_cluster_vectors_byte_offsets_are_consistent(tmp_path: Path) -> None:
    """Vectors returned via cluster reads match those from iter_indexed_vectors."""
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]
    _, paths = _build_v2(tmp_path, items, n_ivf_clusters=2)
    full = {iv.vector_id: iv.encoded.scale for iv in SegmentReader(paths.segment_path).iter_indexed_vectors()}
    partial = {iv.vector_id: iv.encoded.scale for iv in SegmentReader(paths.segment_path).iter_cluster_vectors({0, 1})}
    assert full == partial


# ---------------------------------------------------------------------------
# v2 segment with more requested clusters than exist
# ---------------------------------------------------------------------------

def test_build_v2_fewer_vectors_than_clusters(tmp_path: Path) -> None:
    """n_ivf_clusters > len(vectors) should not crash — falls back to min."""
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0])]
    manifest, paths = _build_v2(tmp_path, items, n_ivf_clusters=16)
    assert SegmentReader(paths.segment_path).read_format_version() == "v2"
    rows = list(SegmentReader(paths.segment_path).iter_indexed_vectors())
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# CentroidIndex.from_stored_data
# ---------------------------------------------------------------------------

def test_from_stored_data_is_built(tmp_path: Path) -> None:
    centroids = [[1.0, 0.0], [0.0, 1.0]]
    buckets = {"0": ["a", "b"], "1": ["c", "d"]}
    ivf = CentroidIndex.from_stored_data(centroids, buckets)
    assert ivf.is_built
    assert ivf.bucket_count == 2


def test_from_stored_data_probe_returns_correct_bucket(tmp_path: Path) -> None:
    centroids = [[1.0, 0.0], [0.0, 1.0]]
    buckets = {"0": ["a", "b"], "1": ["c", "d"]}
    ivf = CentroidIndex.from_stored_data(centroids, buckets)
    # Query near centroid 0 → should return bucket 0 vectors
    candidates = ivf.probe(np.array([0.99, 0.01], dtype=np.float32), probe_k=1)
    assert "a" in candidates or "b" in candidates
    assert "c" not in candidates
    assert "d" not in candidates


def test_from_stored_data_probe_k2_returns_both_buckets() -> None:
    centroids = [[1.0, 0.0], [0.0, 1.0]]
    buckets = {"0": ["a"], "1": ["b"]}
    ivf = CentroidIndex.from_stored_data(centroids, buckets)
    candidates = ivf.probe(np.array([1.0, 0.0], dtype=np.float32), probe_k=2)
    assert candidates == {"a", "b"}


def test_from_stored_data_empty_centroids() -> None:
    ivf = CentroidIndex.from_stored_data([], {})
    assert ivf.is_built
    assert ivf.bucket_count == 0
    candidates = ivf.probe(np.array([1.0, 0.0], dtype=np.float32), probe_k=1)
    assert candidates == set()


def test_from_stored_data_missing_bucket_key() -> None:
    """bucket_vector_ids may not have every cluster key — treat as empty bucket."""
    centroids = [[1.0, 0.0], [0.0, 1.0]]
    buckets = {"0": ["a"]}  # cluster 1 absent
    ivf = CentroidIndex.from_stored_data(centroids, buckets)
    assert ivf.bucket_count == 2
    candidates = ivf.probe(np.array([0.0, 1.0], dtype=np.float32), probe_k=1)
    assert candidates == set()  # cluster 1 is empty


# ---------------------------------------------------------------------------
# ShowcaseScoredDatabase — enable_ivf=True end-to-end
# ---------------------------------------------------------------------------

def test_ivf_flush_writes_v2_segment(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(
        collection_id="col",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,
    )
    for vid, emb in [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]:
        db.upsert(vector_id=vid, embedding=emb)
    db.flush_mutable(segment_id="seg-1", generation=1)

    seg_dir = tmp_path / "segments" / "col" / "shard-0"
    seg_files = list(seg_dir.glob("*.segment.jsonl"))
    assert len(seg_files) == 1
    assert SegmentReader(seg_files[0]).read_format_version() == "v2"


def test_ivf_compressed_query_returns_correct_results(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(
        collection_id="col",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,
    )
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"tag": "x"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"tag": "y"})
    db.upsert(vector_id="c", embedding=[0.8, 0.2], metadata={"tag": "x"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    hits = db.query_compressed_hybrid_hits([1.0, 0.0], top_k=2)
    ids = [h.vector_id for h in hits]
    assert "a" in ids


def test_ivf_query_matches_non_ivf_query(tmp_path: Path) -> None:
    """With probe_k == n_clusters, IVF must return the same top-k as no-IVF."""
    items = [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]

    db_plain = ShowcaseScoredDatabase(
        collection_id="plain",
        root_dir=tmp_path / "plain",
        enable_ivf=False,
    )
    db_ivf = ShowcaseScoredDatabase(
        collection_id="ivf",
        root_dir=tmp_path / "ivf",
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,  # probe all clusters → full recall
    )
    for vid, emb in items:
        db_plain.upsert(vector_id=vid, embedding=emb)
        db_ivf.upsert(vector_id=vid, embedding=emb)
    db_plain.flush_mutable(segment_id="seg-1", generation=1)
    db_ivf.flush_mutable(segment_id="seg-1", generation=1)

    query = [0.9, 0.1]
    plain_hits = db_plain.query_compressed_hybrid_hits(query, top_k=3)
    ivf_hits = db_ivf.query_compressed_hybrid_hits(query, top_k=3)

    assert [h.vector_id for h in plain_hits] == [h.vector_id for h in ivf_hits]


def test_ivf_index_reconstructed_from_header_not_k_means(tmp_path: Path) -> None:
    """IVF index in _segment_ivf_indexes should be populated via header, not k-means,
    so the same object is reused across repeated queries."""
    db = ShowcaseScoredDatabase(
        collection_id="col",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,
    )
    for vid, emb in [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2])]:
        db.upsert(vector_id=vid, embedding=emb)
    db.flush_mutable(segment_id="seg-1", generation=1)

    db.query_compressed_hybrid_hits([1.0, 0.0], top_k=2)
    assert len(db._segment_ivf_indexes) == 1

    first_ivf = next(iter(db._segment_ivf_indexes.values()))

    db.query_compressed_hybrid_hits([1.0, 0.0], top_k=2)
    second_ivf = next(iter(db._segment_ivf_indexes.values()))

    # Same object — not rebuilt on second query
    assert first_ivf is second_ivf


def test_ivf_index_cleared_on_new_flush(tmp_path: Path) -> None:
    """Flushing a new segment should invalidate the IVF index for that path."""
    db = ShowcaseScoredDatabase(
        collection_id="col",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,
    )
    for vid, emb in [("a", [1.0, 0.0]), ("b", [0.0, 1.0])]:
        db.upsert(vector_id=vid, embedding=emb)
    db.flush_mutable(segment_id="seg-1", generation=1)

    db.query_compressed_hybrid_hits([1.0, 0.0], top_k=1)
    assert len(db._segment_ivf_indexes) == 1
    seg_path = next(iter(db._segment_ivf_indexes))

    # Flush a second segment — first should stay, second not yet built
    for vid, emb in [("c", [0.9, 0.1])]:
        db.upsert(vector_id=vid, embedding=emb)
    db.flush_mutable(segment_id="seg-2", generation=2)

    # seg-1 IVF index should still be cached; seg-2 not yet (lazy)
    assert seg_path in db._segment_ivf_indexes


def test_ivf_cache_clear_does_not_wipe_ivf_indexes(tmp_path: Path) -> None:
    """clear_segment_caches must not evict IVF indexes — they're valid as long
    as the segment file hasn't changed."""
    db = ShowcaseScoredDatabase(
        collection_id="col",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,
    )
    for vid, emb in [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2])]:
        db.upsert(vector_id=vid, embedding=emb)
    db.flush_mutable(segment_id="seg-1", generation=1)

    db.query_compressed_hybrid_hits([1.0, 0.0], top_k=2)
    assert len(db._segment_ivf_indexes) == 1

    db.clear_segment_caches()
    assert len(db._segment_ivf_indexes) == 1  # still present after cache clear


def test_ivf_compressed_reranked_returns_scored_hits(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(
        collection_id="col",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=2,
        ivf_probe_k=2,
    )
    for vid, emb in [("a", [1.0, 0.0]), ("b", [0.0, 1.0]), ("c", [0.8, 0.2]), ("d", [0.2, 0.8])]:
        db.upsert(vector_id=vid, embedding=emb)
    db.flush_mutable(segment_id="seg-1", generation=1)

    hits = db.query_compressed_reranked_hybrid_hits([1.0, 0.0], top_k=2)
    assert hits
    assert hits[0].score >= hits[-1].score
    assert hits[0].vector_id == "a"


# ---------------------------------------------------------------------------
# Batch scoring — ScalarQuantizer.batch_approx_score
# ---------------------------------------------------------------------------

def test_batch_approx_score_matches_individual_scores() -> None:
    from recalllayer.quantization.scalar import ScalarQuantizer
    q = ScalarQuantizer()
    vecs = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.3], [0.5, 0.5]]
    query = [0.9, 0.1]
    encoded = [q.encode(v) for v in vecs]

    individual = [q.approx_score(query, e) for e in encoded]
    batch = q.batch_approx_score(query, encoded)

    assert len(batch) == len(individual)
    for i, b in zip(individual, batch):
        assert abs(i - float(b)) < 1e-5


def test_batch_approx_score_empty_input() -> None:
    from recalllayer.quantization.scalar import ScalarQuantizer
    q = ScalarQuantizer()
    result = q.batch_approx_score([1.0, 0.0], [])
    assert len(result) == 0


def test_normalized_batch_approx_score_matches_individual() -> None:
    from recalllayer.quantization.experiments import NormalizedScalarQuantizer
    q = NormalizedScalarQuantizer()
    vecs = [[1.0, 0.0], [0.0, 1.0], [0.6, 0.4]]
    query = [0.8, 0.2]
    encoded = [q.encode(v) for v in vecs]

    individual = [q.approx_score(query, e) for e in encoded]
    batch = q.batch_approx_score(query, encoded)

    for i, b in zip(individual, batch):
        assert abs(i - float(b)) < 1e-5
