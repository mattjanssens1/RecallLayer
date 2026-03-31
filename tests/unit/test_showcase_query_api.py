from types import SimpleNamespace

from turboquant_db.api.schemas import QueryRequest
from turboquant_db.api.showcase_query_api import QuerySurfaceRunner, build_mode_name, build_scored_query_response, count_hit_sources, segment_ids_for_paths


class _FakeMutableEntry:
    def __init__(self, *, deleted: bool = False) -> None:
        self.record = SimpleNamespace(is_deleted=deleted)


class _FakeMutableBuffer:
    def __init__(self) -> None:
        self.entries = {"mutable-1": _FakeMutableEntry()}

    def get(self, vector_id: str):
        return self.entries.get(vector_id)


class _FakeDb:
    def __init__(self) -> None:
        self.mutable_buffer = _FakeMutableBuffer()

    def query_exact_hybrid_hits(self, embedding, *, top_k, filters):
        return [SimpleNamespace(vector_id="exact-1")]

    def query_compressed_hybrid_hits(self, embedding, *, top_k, filters):
        return [SimpleNamespace(vector_id="approx-1")]

    def query_compressed_reranked_hybrid_hits(self, embedding, *, top_k, filters):
        return [SimpleNamespace(vector_id="rerank-1")]


def test_query_surface_runner_dispatches_modes() -> None:
    runner = QuerySurfaceRunner(db=_FakeDb())

    exact_hits, exact_mode, exact_candidate_k = runner.execute_hits(
        QueryRequest(embedding=[1.0], top_k=2, approximate=False, rerank=False, filters={})
    )
    compressed_hits, compressed_mode, compressed_candidate_k = runner.execute_hits(
        QueryRequest(embedding=[1.0], top_k=2, approximate=True, rerank=False, filters={})
    )
    reranked_hits, reranked_mode, reranked_candidate_k = runner.execute_hits(
        QueryRequest(embedding=[1.0], top_k=2, approximate=True, rerank=True, filters={})
    )

    assert exact_hits[0].vector_id == "exact-1"
    assert exact_mode == "exact-hybrid"
    assert exact_candidate_k is None
    assert compressed_hits[0].vector_id == "approx-1"
    assert compressed_mode == "compressed-hybrid"
    assert compressed_candidate_k is None
    assert reranked_hits[0].vector_id == "rerank-1"
    assert reranked_mode == "compressed-reranked-hybrid"
    assert reranked_candidate_k == 8


def test_query_surface_helpers_cover_mode_names_source_counts_segments_and_scored_response() -> None:
    db = _FakeDb()
    hits = [SimpleNamespace(vector_id="mutable-1", score=0.9, metadata={"region": "us"}), SimpleNamespace(vector_id="sealed-1", score=0.8, metadata={"region": "ca"})]

    mutable_hit_count, sealed_hit_count = count_hit_sources(db=db, hits=hits)
    response = build_scored_query_response(hits=hits, base_mode="compressed-hybrid")

    assert build_mode_name("compressed-hybrid", suffix="observed") == "compressed-hybrid-observed"
    assert mutable_hit_count == 1
    assert sealed_hit_count == 1
    assert segment_ids_for_paths(["/tmp/a.seg", "/tmp/b.seg"]) == ["a.seg", "b.seg"]
    assert response.mode == "compressed-hybrid-scored"
    assert response.results[0].vector_id == "mutable-1"
