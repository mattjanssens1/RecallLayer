from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(slots=True)
class MetadataRow:
    vector_id: str
    metadata: dict[str, Any]


class FilterIndexes:
    """Exact metadata indexes for keyword, boolean, and numeric filters."""

    def __init__(self, rows: Iterable[MetadataRow]) -> None:
        self._all_ids: set[str] = set()
        self._exact_values: dict[str, dict[Any, set[str]]] = defaultdict(lambda: defaultdict(set))
        self._sorted_numeric: dict[str, list[tuple[float, str]]] = defaultdict(list)

        for row in rows:
            self._all_ids.add(row.vector_id)
            for key, value in row.metadata.items():
                if isinstance(value, (str, bool, int, float)):
                    self._exact_values[key][value].add(row.vector_id)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self._sorted_numeric[key].append((float(value), row.vector_id))

        for key in self._sorted_numeric:
            self._sorted_numeric[key].sort(key=lambda item: item[0])

    @property
    def all_ids(self) -> set[str]:
        return set(self._all_ids)

    def select_ids(self, filters: dict[str, Any]) -> set[str]:
        if not filters:
            return self.all_ids

        selected = self.all_ids
        for key, condition in filters.items():
            selected &= self._select_for_condition(key, condition)
            if not selected:
                break
        return selected

    def estimate_selectivity(self, filters: dict[str, Any]) -> float:
        if not self._all_ids:
            return 0.0
        return len(self.select_ids(filters)) / float(len(self._all_ids))

    def _select_for_condition(self, key: str, condition: Any) -> set[str]:
        if not isinstance(condition, dict):
            return set(self._exact_values.get(key, {}).get(condition, set()))

        matches: set[str] | None = None
        if "eq" in condition:
            matches = set(self._exact_values.get(key, {}).get(condition["eq"], set()))
        if "in" in condition:
            in_matches: set[str] = set()
            for value in condition["in"]:
                in_matches |= set(self._exact_values.get(key, {}).get(value, set()))
            matches = in_matches if matches is None else matches & in_matches
        if "gte" in condition or "lte" in condition:
            range_matches = self._select_numeric_range(
                key,
                gte=condition.get("gte"),
                lte=condition.get("lte"),
            )
            matches = range_matches if matches is None else matches & range_matches

        return matches or set()

    def _select_numeric_range(self, key: str, *, gte: Any = None, lte: Any = None) -> set[str]:
        values = self._sorted_numeric.get(key, [])
        if not values:
            return set()

        numeric_values = [value for value, _vector_id in values]
        left = bisect_left(numeric_values, float(gte)) if gte is not None else 0
        right = bisect_right(numeric_values, float(lte)) if lte is not None else len(values)
        return {vector_id for _value, vector_id in values[left:right]}
