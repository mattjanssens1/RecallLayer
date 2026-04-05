from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(slots=True)
class EncodedVector:
    """Generic encoded vector payload for approximate scoring."""

    codes: np.ndarray
    scale: float

    @property
    def code_size_bytes(self) -> int:
        return int(self.codes.nbytes)


class Quantizer(ABC):
    """Base interface for approximate vector encoding and scoring."""

    @abstractmethod
    def encode(self, vector: Sequence[float]) -> EncodedVector:
        raise NotImplementedError

    def batch_encode(self, vectors: Sequence[Sequence[float]]) -> list[EncodedVector]:
        return [self.encode(vector) for vector in vectors]

    @abstractmethod
    def approx_score(self, query_vector: Sequence[float], encoded: EncodedVector) -> float:
        raise NotImplementedError

    def batch_approx_score(
        self,
        query_vector: Sequence[float],
        encoded_vectors: Sequence[EncodedVector],
    ) -> np.ndarray:
        return np.asarray(
            [self.approx_score(query_vector=query_vector, encoded=encoded) for encoded in encoded_vectors],
            dtype=np.float32,
        )
