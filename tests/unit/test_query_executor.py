from turboquant_db.engine.mutable_buffer import MutableBuffer
from turboquant_db.engine.query_executor import QueryExecutor
from turboquant_db.quantization.scalar import ScalarQuantizer


def test_query_executor_exact_and_compressed_agree_on_simple_case() -> None:
    buffer = MutableBuffer(collection_id="documents")
    buffer.upsert(
        vector_id="a",
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=1,
    )
    buffer.upsert(
        vector_id="b",
        embedding=[0.0, 1.0],
        metadata={"region": "ca"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=2,
    )

    executor = QueryExecutor(mutable_buffer=buffer, quantizer=ScalarQuantizer())

    exact = executor.search_exact([0.9, 0.1], top_k=1)
    compressed = executor.search_compressed([0.9, 0.1], top_k=1)

    assert exact[0].vector_id == "a"
    assert compressed[0].vector_id == "a"


def test_query_executor_filter_is_applied() -> None:
    buffer = MutableBuffer(collection_id="documents")
    buffer.upsert(
        vector_id="a",
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=1,
    )
    buffer.upsert(
        vector_id="b",
        embedding=[0.9, 0.1],
        metadata={"region": "ca"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=2,
    )

    executor = QueryExecutor(mutable_buffer=buffer, quantizer=ScalarQuantizer())
    results = executor.search_exact(
        [1.0, 0.0],
        top_k=2,
        filter_fn=lambda metadata: metadata.get("region") == "ca",
    )

    assert [result.vector_id for result in results] == ["b"]


def test_query_executor_exact_candidate_restriction_only_scores_selected_ids() -> None:
    buffer = MutableBuffer(collection_id="documents")
    buffer.upsert(
        vector_id="a",
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=1,
    )
    buffer.upsert(
        vector_id="b",
        embedding=[0.0, 1.0],
        metadata={"region": "ca"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=2,
    )

    executor = QueryExecutor(mutable_buffer=buffer, quantizer=ScalarQuantizer())

    restricted = executor.search_exact([1.0, 0.0], top_k=2, candidate_ids={"b"})
    empty = executor.search_exact([1.0, 0.0], top_k=2, candidate_ids=set())

    assert [result.vector_id for result in restricted] == ["b"]
    assert empty == []


def test_query_executor_compressed_candidate_restriction_only_scores_selected_ids() -> None:
    buffer = MutableBuffer(collection_id="documents")
    buffer.upsert(
        vector_id="a",
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=1,
    )
    buffer.upsert(
        vector_id="b",
        embedding=[0.0, 1.0],
        metadata={"region": "ca"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=2,
    )

    executor = QueryExecutor(mutable_buffer=buffer, quantizer=ScalarQuantizer())

    restricted = executor.search_compressed([1.0, 0.0], top_k=2, candidate_ids={"b"})
    empty = executor.search_compressed([1.0, 0.0], top_k=2, candidate_ids=set())

    assert [result.vector_id for result in restricted] == ["b"]
    assert empty == []
