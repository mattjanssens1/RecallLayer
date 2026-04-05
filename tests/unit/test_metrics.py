from recalllayer.benchmark.metrics import average_latency_ms, recall_at_k, top_k_overlap


def test_recall_at_k() -> None:
    value = recall_at_k(expected_ids=["a", "b"], actual_ids=["a", "c"], k=2)
    assert value == 0.5


def test_top_k_overlap() -> None:
    value = top_k_overlap(left_ids=["a", "b"], right_ids=["b", "c"], k=2)
    assert value == 1.0 / 3.0


def test_average_latency_ms() -> None:
    value = average_latency_ms([10.0, 20.0, 30.0])
    assert value == 20.0
