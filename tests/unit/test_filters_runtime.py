from recalllayer.filter_eval import build_filter_fn


def test_filters_runtime_predicate() -> None:
    predicate = build_filter_fn({"region": {"eq": "us"}})
    assert predicate({"region": "us"}) is True
    assert predicate({"region": "ca"}) is False
