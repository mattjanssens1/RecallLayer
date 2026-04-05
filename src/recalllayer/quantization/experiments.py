from __future__ import annotations

from typing import Sequence

import numpy as np

from recalllayer.quantization.base import EncodedVector, Quantizer
from recalllayer.quantization.scalar import ScalarQuantizer
from recalllayer.quantization.turboquant_adapter import TurboQuantAdapter


class NormalizedScalarQuantizer(Quantizer):
    """Quantizer variant that L2-normalizes vectors before scalar coding."""

    def __init__(self, levels: int = 127) -> None:
        self.inner = ScalarQuantizer(levels=levels)
        self.name = f"normalized-{self.inner.name}"

    def encode(self, vector: Sequence[float]) -> EncodedVector:
        arr = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        normalized = arr if norm == 0.0 else arr / norm
        return self.inner.encode(normalized.tolist())

    def approx_score(self, query_vector: Sequence[float], encoded: EncodedVector) -> float:
        arr = np.asarray(query_vector, dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        normalized = arr if norm == 0.0 else arr / norm
        return self.inner.approx_score(normalized.tolist(), encoded)


class ShiftedTurboQuantAdapter(TurboQuantAdapter):
    """Small experimental variant that shifts the rotation amount."""

    def __init__(self, levels: int = 127, shift: int = 2) -> None:
        super().__init__(levels=levels)
        self.shift = shift
        self.name = f"shifted-turboquant-adapter-{levels}-s{shift}"

    def encode(self, vector: Sequence[float]) -> EncodedVector:
        arr = np.asarray(vector, dtype=np.float32)
        if arr.size == 0:
            return EncodedVector(codes=np.asarray([], dtype=np.int8), scale=1.0)
        rotated = np.roll(arr, shift=self.shift)
        max_abs = float(np.max(np.abs(rotated))) if rotated.size else 0.0
        scale = max_abs / float(self.levels) if max_abs > 0.0 else 1.0
        codes = np.clip(np.rint(rotated / scale), -self.levels, self.levels).astype(np.int8)
        return EncodedVector(codes=codes, scale=scale)

    def approx_score(self, query_vector: Sequence[float], encoded: EncodedVector) -> float:
        query = np.asarray(query_vector, dtype=np.float32)
        rotated_query = np.roll(query, shift=self.shift)
        reconstructed = encoded.codes.astype(np.float32) * np.float32(encoded.scale)
        return float(np.dot(rotated_query, reconstructed))
