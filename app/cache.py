"""A tiny in-process TTL cache, keyed by stop code.

Sufficient for a single-process deployment. For multi-worker / multi-host setups,
swap this for Redis behind the same ``get`` / ``set`` interface.
"""

from __future__ import annotations

import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: T) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        self._store.clear()
