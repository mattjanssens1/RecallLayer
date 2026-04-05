from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from turboquant_db.filters.indexes import FilterIndexes


class FilterStrategy(StrEnum):
    PRE_FILTER = "pre-filter"
    POST_FILTER = "post-filter"
    NO_FILTER = "no-filter"


@dataclass(slots=True)
class FilterPlan:
    strategy: FilterStrategy
    estimated_selectivity: float
    candidate_ids: set[str]


class FilterPlanner:
    """Pick a simple exact-filter strategy before retrieval or rerank."""

    def __init__(self, *, prefilter_threshold: float = 0.35) -> None:
        self.prefilter_threshold = prefilter_threshold

    def plan(self, *, filters: dict[str, object], indexes: FilterIndexes | None) -> FilterPlan:
        if not filters:
            return FilterPlan(strategy=FilterStrategy.NO_FILTER, estimated_selectivity=1.0, candidate_ids=set())
        if indexes is None:
            return FilterPlan(strategy=FilterStrategy.POST_FILTER, estimated_selectivity=1.0, candidate_ids=set())

        candidate_ids = indexes.select_ids(filters)
        estimated_selectivity = indexes.estimate_selectivity(filters)
        strategy = (
            FilterStrategy.PRE_FILTER
            if estimated_selectivity <= self.prefilter_threshold
            else FilterStrategy.POST_FILTER
        )
        return FilterPlan(
            strategy=strategy,
            estimated_selectivity=estimated_selectivity,
            candidate_ids=candidate_ids,
        )
