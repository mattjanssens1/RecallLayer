from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Iterable, Literal

from recalllayer.filter_eval import build_filter_fn
from recalllayer.retrieval.base import Candidate

SearchMode = Literal["exact", "compressed"]


@dataclass(slots=True)
class HybridSearchInputs:
    query_vector: list[float]
    top_k: int
    filters: dict[str, Any] | None = None
    candidate_ids: set[str] | None = None


@dataclass(slots=True)
class HybridSearchResult:
    ranked_hits: list[Candidate]
    mutable_candidates: list[Candidate]
    sealed_candidates: list[Candidate]
    source_map: dict[str, str]
    mutable_search_latency_ms: float
    sealed_search_latency_ms: float
    merge_latency_ms: float


@dataclass(slots=True)
class HybridRerankResult:
    final_hits: list[Candidate]
    source_map: dict[str, str]
    rerank_latency_ms: float


def run_hybrid_search(
    *,
    inputs: HybridSearchInputs,
    mutable_search: Callable[[list[float], int, Callable[[dict[str, Any]], bool] | None, set[str] | None], list[Candidate]],
    sealed_search: Callable[[list[float], int, dict[str, Any] | None, set[str] | None], list[Candidate]],
    mode: SearchMode,
    prefer_mutable_on_ties: bool = True,
) -> HybridSearchResult:
    filter_fn = build_filter_fn(inputs.filters or {})
    mutable_filter = None if inputs.candidate_ids is not None else filter_fn
    sealed_filters = None if inputs.candidate_ids is not None else inputs.filters

    mutable_start = perf_counter()
    mutable_candidates = mutable_search(inputs.query_vector, inputs.top_k, mutable_filter, inputs.candidate_ids)
    mutable_search_latency_ms = (perf_counter() - mutable_start) * 1000.0

    sealed_start = perf_counter()
    sealed_candidates = sealed_search(inputs.query_vector, inputs.top_k, sealed_filters, inputs.candidate_ids)
    sealed_search_latency_ms = (perf_counter() - sealed_start) * 1000.0

    merge_start = perf_counter()
    ranked_hits, source_map = merge_hybrid_candidates(
        mutable_candidates=mutable_candidates,
        sealed_candidates=sealed_candidates,
        top_k=inputs.top_k,
        prefer_mutable_on_ties=prefer_mutable_on_ties,
    )
    merge_latency_ms = (perf_counter() - merge_start) * 1000.0

    return HybridSearchResult(
        ranked_hits=ranked_hits,
        mutable_candidates=mutable_candidates,
        sealed_candidates=sealed_candidates,
        source_map=source_map,
        mutable_search_latency_ms=mutable_search_latency_ms,
        sealed_search_latency_ms=sealed_search_latency_ms,
        merge_latency_ms=merge_latency_ms,
    )


def rerank_hybrid_candidates(
    *,
    candidate_ids: Iterable[str],
    top_k: int,
    mutable_exact_search: Callable[[list[float], int, Callable[[dict[str, Any]], bool] | None, set[str] | None], list[Candidate]],
    sealed_exact_search: Callable[[list[float], int, dict[str, Any] | None, set[str] | None], list[Candidate]],
    query_vector: list[float],
    prefer_mutable_on_ties: bool = True,
) -> HybridRerankResult:
    candidate_id_set = set(candidate_ids)
    rerank_start = perf_counter()
    rescored_mutable = mutable_exact_search(query_vector, len(candidate_id_set), None, candidate_id_set)
    rescored_sealed = sealed_exact_search(query_vector, len(candidate_id_set), None, candidate_id_set)
    final_hits, source_map = merge_hybrid_candidates(
        mutable_candidates=rescored_mutable,
        sealed_candidates=rescored_sealed,
        top_k=top_k,
        prefer_mutable_on_ties=prefer_mutable_on_ties,
    )
    rerank_latency_ms = (perf_counter() - rerank_start) * 1000.0
    return HybridRerankResult(final_hits=final_hits, source_map=source_map, rerank_latency_ms=rerank_latency_ms)


def merge_hybrid_candidates(
    *,
    mutable_candidates: list[Candidate],
    sealed_candidates: list[Candidate],
    top_k: int,
    prefer_mutable_on_ties: bool = True,
) -> tuple[list[Candidate], dict[str, str]]:
    merged: dict[str, Candidate] = {}
    source_map: dict[str, str] = {}

    for candidate in sealed_candidates:
        merged[candidate.vector_id] = candidate
        source_map[candidate.vector_id] = "sealed"

    for candidate in mutable_candidates:
        current = merged.get(candidate.vector_id)
        if current is None or candidate.score > current.score or (prefer_mutable_on_ties and candidate.score == current.score):
            merged[candidate.vector_id] = candidate
            source_map[candidate.vector_id] = "mutable"

    ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
    return ranked[:top_k], source_map
