from turboquant_db.filters.indexes import FilterIndexes, MetadataRow
from turboquant_db.filters.planner import FilterPlanner, FilterStrategy


def _rows() -> list[MetadataRow]:
    return [
        MetadataRow(vector_id="a", metadata={"region": "us", "active": True, "score": 10, "age_days": 2}),
        MetadataRow(vector_id="b", metadata={"region": "us", "active": False, "score": 5, "age_days": 10}),
        MetadataRow(vector_id="c", metadata={"region": "ca", "active": True, "score": 7, "age_days": 20}),
        MetadataRow(vector_id="d", metadata={"region": "uk", "active": True, "score": 2, "age_days": 40}),
    ]


def test_filter_indexes_support_eq_and_in() -> None:
    indexes = FilterIndexes(_rows())

    assert indexes.select_ids({"region": {"eq": "us"}}) == {"a", "b"}
    assert indexes.select_ids({"region": {"in": ["us", "ca"]}}) == {"a", "b", "c"}


def test_filter_indexes_support_numeric_ranges() -> None:
    indexes = FilterIndexes(_rows())

    assert indexes.select_ids({"score": {"gte": 6}}) == {"a", "c"}
    assert indexes.select_ids({"age_days": {"gte": 5, "lte": 20}}) == {"b", "c"}


def test_filter_indexes_intersect_multiple_conditions() -> None:
    indexes = FilterIndexes(_rows())

    assert indexes.select_ids({"region": {"eq": "us"}, "active": {"eq": True}}) == {"a"}


def test_filter_planner_chooses_prefilter_for_selective_queries() -> None:
    indexes = FilterIndexes(_rows())
    planner = FilterPlanner(prefilter_threshold=0.30)

    plan = planner.plan(filters={"region": {"eq": "uk"}}, indexes=indexes)

    assert plan.strategy == FilterStrategy.PRE_FILTER
    assert plan.candidate_ids == {"d"}
    assert plan.estimated_selectivity == 0.25


def test_filter_planner_chooses_postfilter_for_broad_queries() -> None:
    indexes = FilterIndexes(_rows())
    planner = FilterPlanner(prefilter_threshold=0.30)

    plan = planner.plan(filters={"active": {"eq": True}}, indexes=indexes)

    assert plan.strategy == FilterStrategy.POST_FILTER
    assert plan.candidate_ids == {"a", "c", "d"}
    assert plan.estimated_selectivity == 0.75
