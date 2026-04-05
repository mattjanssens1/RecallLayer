"""LRU segment read cache: caches decoded segment contents by segment path."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from threading import Lock
from recalllayer.retrieval.base import IndexedVector


class SegmentReadCache:
    """Cache decoded segment contents (IndexedVector list) by segment path.

    Provides LRU eviction and manual invalidation.

    Args:
        max_size: Maximum number of segments to keep in cache (default 8).
    """

    def __init__(self, max_size: int = 8) -> None:
        self._max_size = max(1, max_size)
        self._cache: OrderedDict[str, list[IndexedVector]] = OrderedDict()
        self._lock = Lock()

    def get(self, path: Path | str) -> list[IndexedVector] | None:
        """Return cached contents for *path*, or None if not cached.

        Moves the entry to most-recently-used position on hit.
        """
        key = str(path)
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, path: Path | str, vectors: list[IndexedVector]) -> None:
        """Store *vectors* for *path*, evicting LRU entry if at capacity."""
        key = str(path)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = vectors
            else:
                self._cache[key] = vectors
                if len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)

    def invalidate(self, path: Path | str) -> bool:
        """Remove a specific path from the cache. Returns True if it was present."""
        key = str(path)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all entries whose path starts with *prefix*. Returns count removed."""
        with self._lock:
            to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in to_remove:
                del self._cache[k]
            return len(to_remove)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of cached segments."""
        with self._lock:
            return len(self._cache)

    @property
    def max_size(self) -> int:
        return self._max_size
