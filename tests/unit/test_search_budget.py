from __future__ import annotations

import numpy as np

from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.scalar import ScalarQuantizer


def _build_dataset(n_items: int = 120, dim: int = 16, seed: int = 9):
    rng = np.random.default_rng(seed)
    centroid_a = rng.standard_normal(dim).astype(np.float32)
    centroid_a /= np.linalg.norm(centroid_a)
    centroid_b = rng.standard_normal(dim).astype(np.float32)
    centroid_b /= np.linalg.norm(centroid_b)

    items: list[tuple[str, list[float]]] = []
    for idx in range(n_items):
        base = centroid_a if idx % 2 == 0 else centroid_b
        noise = rng.standard_normal(dim).astype(np.float32) * 0.04
        vec = base + noise
        vec /= np.linalg.norm(vec)
        items.append((f"v-{idx}", vec.tolist()))

    query = ((centroid_a + centroid_b) / 2.0).astype(np.float32)
    query /= np.linalg.norm(query)
    return items, query.tolist()


def _recall(ids: list[str], ground_truth: set[str]) -> float:
    return len(set(ids) & ground_truth) / len(ground_truth)


def test_wider_search_budget_improves_or_matches_recall(tmp_path) -> None:
    items, query = _build_dataset()
    db = ShowcaseScoredDatabase(
        collection_id="budget-test",
        root_dir=tmp_path,
        quantizer=ScalarQuantizer(),
        enable_ivf=True,
        ivf_n_clusters=8,
        ivf_probe_k=2,
        rerank_probe_k=4,
        enable_segment_cache=False,
    )
    for vector_id, embedding in items:
        db.upsert(vector_id=vector_id, embedding=embedding, metadata={})
    db.flush_mutable(segment_id="seg-1", generation=1)

    ground_truth = set(db.query_exact_hybrid(query, top_k=10))
    narrow = db.query_compressed_hybrid(query, top_k=10, search_budget=10)
    wide = db.query_compressed_hybrid(query, top_k=10, search_budget=40)

    assert _recall(wide, ground_truth) >= _recall(narrow, ground_truth)


def test_reranked_search_budget_plumbs_through_hits_api(tmp_path) -> None:
    items, query = _build_dataset(n_items=80)
    db = ShowcaseScoredDatabase(
        collection_id="budget-hits-test",
        root_dir=tmp_path,
        quantizer=ScalarQuantizer(),
        enable_ivf=True,
        ivf_n_clusters=8,
        ivf_probe_k=1,
        rerank_probe_k=4,
        enable_segment_cache=False,
    )
    for vector_id, embedding in items:
        db.upsert(vector_id=vector_id, embedding=embedding, metadata={})
    db.flush_mutable(segment_id="seg-1", generation=1)

    hits = db.query_compressed_reranked_hybrid_hits(query, top_k=5, search_budget=20)

    assert len(hits) <= 5
    assert all(hit.vector_id for hit in hits)
