from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol


class BenchmarkBackend(Protocol):
    """Minimal interface for a retrievable backend under benchmark."""

    name: str

    def query(self, query_vector: list[float], top_k: int, candidate_k: int | None = None) -> list[str]:
        ...


@dataclass(slots=True)
class BenchmarkResult:
    backend: str
    query_count: int
    elapsed_ms: float


class BenchmarkRunner:
    """Very small starting point for repeatable benchmark execution."""

    def __init__(self, backend: BenchmarkBackend) -> None:
        self.backend = backend

    def run(self, queries: list[list[float]], top_k: int, candidate_k: int | None = None) -> BenchmarkResult:
        start = perf_counter()
        for query_vector in queries:
            self.backend.query(query_vector=query_vector, top_k=top_k, candidate_k=candidate_k)
        elapsed_ms = (perf_counter() - start) * 1000.0
        return BenchmarkResult(
            backend=self.backend.name,
            query_count=len(queries),
            elapsed_ms=elapsed_ms,
        )
