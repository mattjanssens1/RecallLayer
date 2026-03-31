from __future__ import annotations

from typing import Any, Callable

from turboquant_db.api.schemas import QueryRequest, QueryResponse, QueryHit


class QuerySurfaceRunner:
    def __init__(self, *, db: Any) -> None:
        self.db = db

    def execute_hits(self, request: QueryRequest) -> tuple[list[Any], str, int | None]:
        if request.approximate and request.rerank:
            return (
                self.db.query_compressed_reranked_hybrid_hits(
                    request.embedding,
                    top_k=request.top_k,
                    filters=request.filters,
                ),
                "compressed-reranked-hybrid",
                max(request.top_k * 4, request.top_k),
            )
        if request.approximate:
            return (
                self.db.query_compressed_hybrid_hits(
                    request.embedding,
                    top_k=request.top_k,
                    filters=request.filters,
                ),
                "compressed-hybrid",
                None,
            )
        return (
            self.db.query_exact_hybrid_hits(
                request.embedding,
                top_k=request.top_k,
                filters=request.filters,
            ),
            "exact-hybrid",
            None,
        )


def build_mode_name(base_mode: str, *, suffix: str) -> str:
    return f"{base_mode}-{suffix}"


def count_hit_sources(*, db: Any, hits: list[Any]) -> tuple[int, int]:
    mutable_hit_count = 0
    sealed_hit_count = 0
    for hit in hits:
        entry = db.mutable_buffer.get(hit.vector_id)
        if entry is not None and not entry.record.is_deleted:
            mutable_hit_count += 1
        else:
            sealed_hit_count += 1
    return mutable_hit_count, sealed_hit_count


def segment_ids_for_paths(paths: list[str]) -> list[str]:
    return [path.split("/")[-1] for path in paths]


def build_scored_query_response(*, hits: list[Any], base_mode: str) -> QueryResponse:
    return QueryResponse(
        results=[QueryHit(vector_id=hit.vector_id, score=hit.score, metadata=hit.metadata) for hit in hits],
        mode=build_mode_name(base_mode, suffix="scored"),
    )
