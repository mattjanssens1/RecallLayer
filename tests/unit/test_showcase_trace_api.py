from types import SimpleNamespace

from turboquant_db.api.schemas import QueryRequest
from turboquant_db.api.showcase_notes import build_collection_notes
from turboquant_db.api.showcase_trace_api import InspectedSurfaceRunner, build_inspected_trace_payload, build_traced_trace_payload


class _FakeInspectedDb:
    def query_exact_hybrid_inspected(self, embedding, *, top_k, filters):
        return SimpleNamespace(hits=[], inspection=SimpleNamespace(mode='exact-hybrid-engine', top_k=top_k, filters_applied=bool(filters), mutable_live_count=1, sealed_segment_count=0, sealed_segment_ids=[], result_count=0, mutable_hit_count=0, sealed_hit_count=0, pre_filter_candidate_count=1, post_filter_candidate_count=0, rerank_candidate_k=None, search_latency_ms=0.1, rerank_latency_ms=0.0, total_latency_ms=0.2))

    def query_compressed_hybrid_inspected(self, embedding, *, top_k, filters):
        return SimpleNamespace(hits=[], inspection=SimpleNamespace(mode='compressed-hybrid-engine', top_k=top_k, filters_applied=bool(filters), mutable_live_count=1, sealed_segment_count=0, sealed_segment_ids=[], result_count=0, mutable_hit_count=0, sealed_hit_count=0, pre_filter_candidate_count=1, post_filter_candidate_count=0, rerank_candidate_k=None, search_latency_ms=0.1, rerank_latency_ms=0.0, total_latency_ms=0.2))

    def query_compressed_reranked_hybrid_inspected(self, embedding, *, top_k, filters):
        return SimpleNamespace(hits=[], inspection=SimpleNamespace(mode='compressed-reranked-hybrid-engine', top_k=top_k, filters_applied=bool(filters), mutable_live_count=1, sealed_segment_count=0, sealed_segment_ids=[], result_count=0, mutable_hit_count=0, sealed_hit_count=0, pre_filter_candidate_count=1, post_filter_candidate_count=0, rerank_candidate_k=8, search_latency_ms=0.1, rerank_latency_ms=0.1, total_latency_ms=0.3))


class _FakeMutableBuffer:
    def live_entries(self):
        return [object()]


class _FakeScoredDb:
    def __init__(self) -> None:
        self.mutable_buffer = _FakeMutableBuffer()

    def _segment_paths(self):
        return ['/tmp/a.seg']


def test_inspected_surface_runner_dispatches_modes() -> None:
    runner = InspectedSurfaceRunner(db=_FakeInspectedDb())

    exact = runner.execute(QueryRequest(embedding=[1.0], top_k=1, approximate=False, rerank=False, filters={}))
    compressed = runner.execute(QueryRequest(embedding=[1.0], top_k=1, approximate=True, rerank=False, filters={}))
    reranked = runner.execute(QueryRequest(embedding=[1.0], top_k=2, approximate=True, rerank=True, filters={}))

    assert exact.inspection.mode == 'exact-hybrid-engine'
    assert compressed.inspection.mode == 'compressed-hybrid-engine'
    assert reranked.inspection.mode == 'compressed-reranked-hybrid-engine'


def test_trace_payload_builders_produce_expected_shapes() -> None:
    request = QueryRequest(embedding=[1.0], top_k=2, approximate=True, rerank=True, filters={'region': {'eq': 'us'}})
    result = _FakeInspectedDb().query_compressed_reranked_hybrid_inspected([1.0], top_k=2, filters={'region': {'eq': 'us'}})

    inspected_payload = build_inspected_trace_payload(request=request, result=result, collection_id='demo')
    traced_payload = build_traced_trace_payload(
        db=_FakeScoredDb(),
        request=request,
        hits=[SimpleNamespace(vector_id='a')],
        base_mode='compressed-reranked-hybrid',
        collection_id='demo',
    )

    assert inspected_payload['mode'] == 'compressed-reranked-hybrid-engine'
    assert inspected_payload['pre_filter_candidate_estimate'] == 1
    assert inspected_payload['post_filter_candidate_estimate'] == 0
    assert inspected_payload['notes'] == build_collection_notes(collection_id='demo')
    assert traced_payload['mode'] == 'compressed-reranked-hybrid-scored'
    assert traced_payload['sealed_segment_count'] == 1
    assert traced_payload['rerank_candidate_k'] == 8
