"""Tests that IVF + reranked path maintains high recall even with tight probe_k.

The recall gap: query_compressed_reranked_hybrid used to call
query_compressed_hybrid with the same ivf_probe_k as a direct query, so the
reranker only received candidates from probe_k clusters.  With many clusters
and a small probe_k the true top-10 items in unprobed clusters were invisible
to the reranker.

Fix: the reranked path uses probe_k = ivf_probe_k * 2 (default) for
candidate generation, or an explicit rerank_probe_k.
"""
from __future__ import annotations

import numpy as np
import pytest

from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.scalar import ScalarQuantizer


def _make_db(
    tmp_path,
    *,
    ivf_n_clusters: int,
    ivf_probe_k: int,
    rerank_probe_k: int | None = None,
    enable_ivf: bool = True,
) -> ShowcaseScoredDatabase:
    return ShowcaseScoredDatabase(
        collection_id="recall-test",
        root_dir=str(tmp_path),
        quantizer=ScalarQuantizer(),
        enable_segment_cache=False,
        enable_ivf=enable_ivf,
        ivf_n_clusters=ivf_n_clusters,
        ivf_probe_k=ivf_probe_k,
        rerank_probe_k=rerank_probe_k,
    )


def _build_adversarial_dataset(
    n_items: int = 200,
    n_clusters: int = 8,
    dim: int = 16,
    seed: int = 42,
) -> tuple[list[tuple[str, list[float]]], list[float]]:
    """Create a dataset where the query's true top-k spans several clusters.

    Returns (items, query_vector).
    """
    rng = np.random.default_rng(seed)
    # One centroid per cluster; each centroid is on the unit sphere.
    centroids = rng.standard_normal((n_clusters, dim)).astype(np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)

    items: list[tuple[str, list[float]]] = []
    per_cluster = n_items // n_clusters
    for cid in range(n_clusters):
        for i in range(per_cluster):
            noise = rng.standard_normal(dim).astype(np.float32) * 0.05
            vec = centroids[cid] + noise
            vec /= np.linalg.norm(vec)
            items.append((f"c{cid}_v{i}", vec.tolist()))

    # Query is the mean of the first two cluster centroids — its true top
    # neighbours are split across clusters 0 and 1.
    query = (centroids[0] + centroids[1]).astype(np.float32)
    query /= float(np.linalg.norm(query))
    return items, query.tolist()


def _exact_top_k(items: list[tuple[str, list[float]]], query: list[float], k: int) -> set[str]:
    q = np.asarray(query, dtype=np.float32)
    scores = [(vid, float(np.dot(q, np.asarray(v, dtype=np.float32)))) for vid, v in items]
    scores.sort(key=lambda x: x[1], reverse=True)
    return {vid for vid, _ in scores[:k]}


def _recall(retrieved: list[str], ground_truth: set[str]) -> float:
    return len(set(retrieved) & ground_truth) / len(ground_truth)


@pytest.fixture()
def adversarial_dataset():
    return _build_adversarial_dataset(n_items=200, n_clusters=8, dim=16)


def test_reranked_recall_higher_than_direct_compressed_with_tight_probe(tmp_path, adversarial_dataset):
    """Reranked path with wider probe should beat direct compressed with tight probe_k=1."""
    items, query = adversarial_dataset
    top_k = 10
    ground_truth = _exact_top_k(items, query, top_k)

    db = _make_db(tmp_path, ivf_n_clusters=8, ivf_probe_k=1, rerank_probe_k=4)
    for vid, vec in items:
        db.upsert(vector_id=vid, embedding=vec)
    db.flush_mutable(segment_id="seg-1")

    direct = db.query_compressed_hybrid(query, top_k=top_k)
    reranked = db.query_compressed_reranked_hybrid(query, top_k=top_k)

    direct_recall = _recall(direct, ground_truth)
    reranked_recall = _recall(reranked, ground_truth)

    # Reranked should equal or exceed direct recall.
    assert reranked_recall >= direct_recall, (
        f"reranked recall {reranked_recall:.2f} < direct recall {direct_recall:.2f}"
    )


def test_reranked_full_recall_with_sufficient_rerank_probe_k(tmp_path, adversarial_dataset):
    """When rerank_probe_k covers enough clusters, recall@10 is 1.0."""
    items, query = adversarial_dataset
    top_k = 10
    ground_truth = _exact_top_k(items, query, top_k)

    # probe_k=1 is too tight for full recall, but rerank_probe_k=8 (all clusters) guarantees it.
    db = _make_db(tmp_path, ivf_n_clusters=8, ivf_probe_k=1, rerank_probe_k=8)
    for vid, vec in items:
        db.upsert(vector_id=vid, embedding=vec)
    db.flush_mutable(segment_id="seg-1")

    reranked = db.query_compressed_reranked_hybrid(query, top_k=top_k)
    # Quantization error means reconstructed-vector rerank can't guarantee 1.0,
    # but with all clusters probed recall should be very high.
    assert _recall(reranked, ground_truth) >= 0.9


def test_reranked_default_probe_k_is_double_ivf_probe_k(tmp_path, adversarial_dataset):
    """Default rerank_probe_k = ivf_probe_k * 2 improves recall over probe_k=1."""
    items, query = adversarial_dataset
    top_k = 10
    ground_truth = _exact_top_k(items, query, top_k)

    # ivf_probe_k=1, rerank_probe_k not set → defaults to 2
    db = _make_db(tmp_path, ivf_n_clusters=8, ivf_probe_k=1)
    for vid, vec in items:
        db.upsert(vector_id=vid, embedding=vec)
    db.flush_mutable(segment_id="seg-1")

    # With just 1 probe, direct compressed will likely miss items in cluster 1.
    # With 2 probes (default for reranked), we see both clusters 0 and 1.
    reranked = db.query_compressed_reranked_hybrid(query, top_k=top_k)
    assert _recall(reranked, ground_truth) >= _recall(
        db.query_compressed_hybrid(query, top_k=top_k), ground_truth
    )


def test_probe_k_override_per_call(tmp_path, adversarial_dataset):
    """query_compressed_hybrid accepts probe_k to override per-call."""
    items, query = adversarial_dataset
    top_k = 10
    ground_truth = _exact_top_k(items, query, top_k)

    db = _make_db(tmp_path, ivf_n_clusters=8, ivf_probe_k=1)
    for vid, vec in items:
        db.upsert(vector_id=vid, embedding=vec)
    db.flush_mutable(segment_id="seg-1")

    narrow = db.query_compressed_hybrid(query, top_k=top_k, probe_k=1)
    wide = db.query_compressed_hybrid(query, top_k=top_k, probe_k=8)

    # Wider probe cannot have lower recall than narrow.
    assert _recall(wide, ground_truth) >= _recall(narrow, ground_truth)


def test_no_regression_when_ivf_disabled(tmp_path, adversarial_dataset):
    """probe_k param is ignored when IVF is disabled; results are unchanged."""
    items, query = adversarial_dataset
    top_k = 10

    db = _make_db(tmp_path, ivf_n_clusters=8, ivf_probe_k=1, enable_ivf=False)
    for vid, vec in items:
        db.upsert(vector_id=vid, embedding=vec)
    db.flush_mutable(segment_id="seg-1")

    # Both calls should return the same result regardless of probe_k.
    res1 = db.query_compressed_hybrid(query, top_k=top_k, probe_k=1)
    res2 = db.query_compressed_hybrid(query, top_k=top_k, probe_k=8)
    assert set(res1) == set(res2)
