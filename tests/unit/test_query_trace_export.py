from dataclasses import dataclass

from turboquant_db.engine.query_trace_export import build_query_trace_payload


@dataclass(slots=True)
class _TimingBreakdown:
    mutable_search_latency_ms: float
    sealed_search_latency_ms: float
    merge_latency_ms: float
    rerank_latency_ms: float
    materialization_latency_ms: float


@dataclass(slots=True)
class _Inspection:
    mode: str
    total_latency_ms: float
    timing_breakdown: _TimingBreakdown


@dataclass(slots=True)
class _Plan:
    mode: str
    candidate_k: int | None


@dataclass(slots=True)
class _Stats:
    mutable_hit_count: int
    sealed_hit_count: int


def test_build_query_trace_payload_serializes_dataclasses_and_notes() -> None:
    payload = build_query_trace_payload(
        inspection=_Inspection(
            mode="compressed-hybrid",
            total_latency_ms=1.2,
            timing_breakdown=_TimingBreakdown(
                mutable_search_latency_ms=0.2,
                sealed_search_latency_ms=0.3,
                merge_latency_ms=0.1,
                rerank_latency_ms=0.4,
                materialization_latency_ms=0.0,
            ),
        ),
        plan=_Plan(mode="compressed-hybrid", candidate_k=8),
        stats=_Stats(mutable_hit_count=2, sealed_hit_count=1),
        notes={"collection_id": "documents"},
    )

    assert payload["inspection"]["mode"] == "compressed-hybrid"
    assert payload["inspection"]["timing_breakdown"]["mutable_search_latency_ms"] == 0.2
    assert payload["plan"]["candidate_k"] == 8
    assert payload["stats"]["mutable_hit_count"] == 2
    assert payload["notes"]["collection_id"] == "documents"
