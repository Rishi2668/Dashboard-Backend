from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheItem:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._items: dict[str, _CacheItem] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if not item:
            return None
        if item.expires_at < time.monotonic():
            self._items.pop(key, None)
            return None
        return item.value

    async def set(self, key: str, value: Any, ttl_sec: int) -> None:
        async with self._lock:
            self._items[key] = _CacheItem(value=value, expires_at=time.monotonic() + ttl_sec)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._items.pop(key, None)

    async def get_or_set(self, key: str, ttl_sec: int, producer: Callable[[], Any]) -> Any:
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await producer()
        await self.set(key, value, ttl_sec)
        return value


cache = TTLCache()


def dashboard_stats_cache_key(user_id: int) -> str:
    return f"dashboard:stats:v3:{user_id}"


async def invalidate_dashboard_stats_cache(user_id: int) -> None:
    """Clear dashboard stats (heatmap, today hours, etc.) after study/mock changes."""
    await cache.delete(dashboard_stats_cache_key(user_id))
    await cache.delete(f"dashboard:stats:{user_id}")  # legacy key

