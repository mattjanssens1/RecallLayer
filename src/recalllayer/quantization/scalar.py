from __future__ import annotations

from typing import Sequence

import numpy as np

from recalllayer.quantization.base import EncodedVector, Quantizer


class ScalarQuantizer(Quantizer):
    """Simple symmetric int8 quantizer for prototype benchmarking."""

    def __init__(self, levels: int = 127) -> None:
        if levels <= 0:
            raise ValueError("levels must be positive")
        self.levels = levels
        self.name = f"scalar-int8-{levels}"

    def encode(self, vector: Sequence[float]) -> EncodedVector:
        arr = np.asarray(vector, dtype=np.float32)
        max_abs = float(np.max(np.abs(arr))) if arr.size else 0.0
        scale = max_abs / float(self.levels) if max_abs > 0.0 else 1.0
        codes = np.clip(np.rint(arr / scale), -self.levels, self.levels).astype(np.int8)
        return EncodedVector(codes=codes, scale=scale)

    def approx_score(self, query_vector: Sequence[float], encoded: EncodedVector) -> float:
        query = np.asarray(query_vector, dtype=np.float32)
        reconstructed = encoded.codes.astype(np.float32) * np.float32(encoded.scale)
        return float(np.dot(query, reconstructed))

    def batch_approx_score(
        self,
        query_vector: Sequence[float],
        encoded_vectors: Sequence[EncodedVector],
    ) -> np.ndarray:
        if not encoded_vectors:
            return np.empty(0, dtype=np.float32)
        query = np.asarray(query_vector, dtype=np.float32)
        codes = np.stack([ev.codes for ev in encoded_vectors]).astype(np.float32)  # (N, D)
        scales = np.asarray([ev.scale for ev in encoded_vectors], dtype=np.float32)  # (N,)
        reconstructed = codes * scales[:, None]  # (N, D)
        return reconstructed @ query  # (N,)
