from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from turboquant_db.quantization.base import EncodedVector


@dataclass(slots=True)
class Candidate:
    vector_id: str
    score: float
    metadata: dict[str, Any]


@dataclass(slots=True)
class IndexedVector:
    vector_id: str
    encoded: EncodedVector
    metadata: dict[str, Any]


FilterFn = Callable[[dict[str, Any]], bool]


class Retriever(Protocol):
    name: str

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filter_fn: FilterFn | None = None,
    ) -> list[Candidate]:
        ...
