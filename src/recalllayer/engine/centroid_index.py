"""CentroidIndex: simple IVF-style candidate pre-filter for compressed scan."""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from recalllayer.retrieval.base import IndexedVector


@dataclass
class CentroidBucket:
    centroid: np.ndarray
    vector_ids: list[str] = field(default_factory=list)


class CentroidIndex:
    """Cluster vectors into N buckets at index time.

    At query time, probe the nearest *probe_k* buckets and return only
    the vector IDs in those buckets as candidates for full scoring.

    This is intentionally simple (random-init k-means style) — not FAISS quality,
    but a correct, benchmarkable alternative scan path.
    """

    def __init__(self, n_clusters: int = 8) -> None:
        self.n_clusters = n_clusters
        self._buckets: list[CentroidBucket] = []
        self._built = False

    def build(self, vectors: list[IndexedVector], *, quantizer) -> None:
        """Cluster *vectors* into buckets using decoded embeddings.

        Uses a simple k-means style clustering (Lloyd's algorithm, fixed iterations).
        Falls back to 1 bucket when there are fewer vectors than clusters.
        """
        if not vectors:
            self._buckets = []
            self._built = True
            return

        # Decode all vectors to float arrays
        decoded: list[np.ndarray] = []
        ids: list[str] = []
        for iv in vectors:
            decoded.append(quantizer.decode(iv.encoded))
            ids.append(iv.vector_id)

        arr = np.stack(decoded, axis=0)  # (N, D)
        n = len(arr)
        k = min(self.n_clusters, n)

        # Initialize centroids by picking k random rows
        rng = np.random.default_rng(42)
        centroid_indices = rng.choice(n, size=k, replace=False)
        centroids = arr[centroid_indices].copy()

        # Lloyd's iterations
        for _ in range(20):
            # Assign each point to nearest centroid
            dists = np.sum((arr[:, None, :] - centroids[None, :, :]) ** 2, axis=2)  # (N, k)
            assignments = np.argmin(dists, axis=1)  # (N,)
            # Update centroids
            new_centroids = np.zeros_like(centroids)
            counts = np.zeros(k, dtype=int)
            for i, c in enumerate(assignments):
                new_centroids[c] += arr[i]
                counts[c] += 1
            for c in range(k):
                if counts[c] > 0:
                    new_centroids[c] = new_centroids[c] / counts[c]
                else:
                    new_centroids[c] = centroids[c]
            if np.allclose(new_centroids, centroids):
                break
            centroids = new_centroids

        # Build buckets
        self._buckets = [CentroidBucket(centroid=centroids[c]) for c in range(k)]
        for i, c in enumerate(assignments):
            self._buckets[c].vector_ids.append(ids[i])

        self._built = True

    def probe(self, query: np.ndarray, *, probe_k: int) -> set[str]:
        """Return candidate vector IDs from the *probe_k* nearest buckets."""
        if not self._buckets:
            return set()
        probe_k = min(probe_k, len(self._buckets))
        centroids = np.stack([b.centroid for b in self._buckets], axis=0)
        dists = np.sum((centroids - query[None, :]) ** 2, axis=1)
        nearest = np.argsort(dists)[:probe_k]
        candidates: set[str] = set()
        for idx in nearest:
            candidates.update(self._buckets[idx].vector_ids)
        return candidates

    @property
    def is_built(self) -> bool:
        return self._built

    @property
    def bucket_count(self) -> int:
        return len(self._buckets)
