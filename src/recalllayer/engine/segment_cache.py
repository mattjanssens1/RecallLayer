"""LRU segment read cache with simple counters."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class SegmentCacheStats:
    hits: int
    misses: int
    evictions: int
    writes: int
    invalidations: int
    size: int
    max_size: int


class SegmentReadCache(Generic[T]):
    """Cache payloads by segment path.

    Provides LRU eviction and manual invalidation.

    Args:
        max_size: Maximum number of segments to keep in cache (default 8).
    """

    def __init__(self, max_size: int = 8) -> None:
        self._max_size = max(1, max_size)
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._writes = 0
        self._invalidations = 0

    def get(self, path: Path | str) -> T | None:
        """Return cached contents for *path*, or None if not cached.

        Moves the entry to most-recently-used position on hit.
        """
        key = str(path)
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            self._hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, path: Path | str, value: T) -> None:
        """Store *value* for *path*, evicting LRU entry if at capacity."""
        key = str(path)
        with self._lock:
            self._writes += 1
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = value
            else:
                self._cache[key] = value
                if len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)
                    self._evictions += 1

    def invalidate(self, path: Path | str) -> bool:
        """Remove a specific path from the cache. Returns True if it was present."""
        key = str(path)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._invalidations += 1
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all entries whose path starts with *prefix*. Returns count removed."""
        with self._lock:
            to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in to_remove:
                del self._cache[k]
            self._invalidations += len(to_remove)
            return len(to_remove)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._invalidations += len(self._cache)
            self._cache.clear()

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._writes = 0
            self._invalidations = 0

    def stats(self) -> SegmentCacheStats:
        with self._lock:
            return SegmentCacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                writes=self._writes,
                invalidations=self._invalidations,
                size=len(self._cache),
                max_size=self._max_size,
            )

    @property
    def size(self) -> int:
        """Current number of cached segments."""
        with self._lock:
            return len(self._cache)

    @property
    def max_size(self) -> int:
        return self._max_size
