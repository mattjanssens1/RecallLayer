from __future__ import annotations

from typing import Sequence

import numpy as np

from turboquant_db.quantization.base import EncodedVector, Quantizer
from turboquant_db.quantization.scalar import ScalarQuantizer
from turboquant_db.quantization.turboquant_adapter import TurboQuantAdapter


class ResidualScalarQuantizer(Quantizer):
    """Scalar quantizer variant that recenters vectors around their mean."""

    def __init__(self, levels: int = 127) -> None:
        self.inner = ScalarQuantizer(levels=levels)
        self.name = f"residual-{self.inner.name}"

    def encode(self, vector: Sequence[float]) -> EncodedVector:
        arr = np.asarray(vector, dtype=np.float32)
        centered = arr - np.mean(arr) if arr.size else arr
        return self.inner.encode(centered.tolist())

    def approx_score(self, query_vector: Sequence[float], encoded: EncodedVector) -> float:
        arr = np.asarray(query_vector, dtype=np.float32)
        centered = arr - np.mean(arr) if arr.size else arr
        return self.inner.approx_score(centered.tolist(), encoded)


class CenteredTurboQuantAdapter(TurboQuantAdapter):
    """TurboQuant-like adapter variant that mean-centers before transform."""

    def __init__(self, levels: int = 127) -> None:
        super().__init__(levels=levels)
        self.name = f"centered-{self.name}"

    def encode(self, vector: Sequence[float]) -> EncodedVector:
        arr = np.asarray(vector, dtype=np.float32)
        centered = arr - np.mean(arr) if arr.size else arr
        return super().encode(centered.tolist())

    def approx_score(self, query_vector: Sequence[float], encoded: EncodedVector) -> float:
        arr = np.asarray(query_vector, dtype=np.float32)
        centered = arr - np.mean(arr) if arr.size else arr
        return super().approx_score(centered.tolist(), encoded)
