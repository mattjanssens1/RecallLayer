from __future__ import annotations

from typing import Sequence

import numpy as np

from turboquant_db.quantization.base import EncodedVector, Quantizer


class TurboQuantAdapter(Quantizer):
    """Interface-compatible placeholder for a future TurboQuant implementation.

    This is not the real algorithm. It provides a distinct transform path and a
    stable module for the rest of the engine to code against.
    """

    def __init__(self, levels: int = 127) -> None:
        if levels <= 0:
            raise ValueError("levels must be positive")
        self.levels = levels
        self.name = f"turboquant-adapter-{levels}"

    def encode(self, vector: Sequence[float]) -> EncodedVector:
        arr = np.asarray(vector, dtype=np.float32)
        if arr.size == 0:
            return EncodedVector(codes=np.asarray([], dtype=np.int8), scale=1.0)

        rotated = np.roll(arr, shift=1)
        max_abs = float(np.max(np.abs(rotated))) if rotated.size else 0.0
        scale = max_abs / float(self.levels) if max_abs > 0.0 else 1.0
        codes = np.clip(np.rint(rotated / scale), -self.levels, self.levels).astype(np.int8)
        return EncodedVector(codes=codes, scale=scale)

    def approx_score(self, query_vector: Sequence[float], encoded: EncodedVector) -> float:
        query = np.asarray(query_vector, dtype=np.float32)
        rotated_query = np.roll(query, shift=1)
        reconstructed = encoded.codes.astype(np.float32) * np.float32(encoded.scale)
        return float(np.dot(rotated_query, reconstructed))
