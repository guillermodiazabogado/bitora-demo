from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    """Small in-process cache for non-critical read models."""

    def __init__(self, max_entries: int = 128) -> None:
        self.max_entries = max(8, int(max_entries))
        self._items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if not item:
                self._misses += 1
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                self._misses += 1
                return None
            self._items.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._items[key] = (time.monotonic() + max(1, int(ttl_seconds)), value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def invalidate(self, prefix: str = "") -> None:
        with self._lock:
            if prefix:
                keys = [key for key in self._items if key.startswith(prefix)]
                for key in keys:
                    self._items.pop(key, None)
            else:
                self._items.clear()
            self._invalidations += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            requests = self._hits + self._misses
            return {
                "enabled": True,
                "backend": "memory-ttl",
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits * 100 / requests, 1) if requests else 0,
                "size": len(self._items),
                "max_entries": self.max_entries,
                "invalidations": self._invalidations,
            }
