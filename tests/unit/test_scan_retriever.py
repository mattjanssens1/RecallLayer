from recalllayer.quantization.scalar import ScalarQuantizer
from recalllayer.retrieval.base import IndexedVector
from recalllayer.retrieval.scan import CompressedScanRetriever


def test_scan_retriever_returns_best_match_first() -> None:
    quantizer = ScalarQuantizer()
    retriever = CompressedScanRetriever(quantizer=quantizer)

    retriever.add(
        IndexedVector(
            vector_id="a",
            encoded=quantizer.encode([1.0, 0.0]),
            metadata={"region": "us"},
        )
    )
    retriever.add(
        IndexedVector(
            vector_id="b",
            encoded=quantizer.encode([0.0, 1.0]),
            metadata={"region": "ca"},
        )
    )

    results = retriever.search(query_vector=[0.9, 0.1], top_k=1)

    assert len(results) == 1
    assert results[0].vector_id == "a"
