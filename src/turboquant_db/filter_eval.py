from __future__ import annotations

from typing import Any, Callable


def build_filter_fn(filters: dict[str, Any]) -> Callable[[dict[str, Any]], bool]:
    """Build a small exact filter predicate for metadata dictionaries."""

    def predicate(metadata: dict[str, Any]) -> bool:
        for key, condition in filters.items():
            value = metadata.get(key)
            if isinstance(condition, dict):
                if "eq" in condition and value != condition["eq"]:
                    return False
                if "in" in condition and value not in condition["in"]:
                    return False
                if "gte" in condition and value < condition["gte"]:
                    return False
                if "lte" in condition and value > condition["lte"]:
                    return False
                continue
            if value != condition:
                return False
        return True

    return predicate
