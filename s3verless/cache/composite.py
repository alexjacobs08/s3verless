"""Composite cache that chains multiple cache backends."""

from typing import Any, List

from s3verless.cache.base import CacheBackend


class CompositeCache(CacheBackend):
    """Multi-tier cache that checks caches in order.

    This cache chains multiple backends together. On reads, it checks
    each cache in order and populates earlier caches on hits in later ones.
    On writes, it writes to all caches.

    Typical usage:
        cache = CompositeCache([
            LRUCache(max_size=100, default_ttl=60),   # L1: Fast, small
            InMemoryCache(max_size=1000, default_ttl=300),  # L2: Larger
        ])
    """

    def __init__(self, caches: List[CacheBackend]):
        """Initialize the composite cache.

        Args:
            caches: List of cache backends in priority order (first = fastest)
        """
        if not caches:
            raise ValueError("At least one cache backend is required")
        self._caches = caches

    async def get(self, key: str, ttl: int | None = None) -> Any | None:
        """Get a value, checking caches in order.

        If found in a later cache, the value is promoted to earlier caches.

        Args:
            key: The cache key
            ttl: Optional TTL to use when promoting to earlier caches

        Returns:
            The cached value or None if not found
        """
        for i, cache in enumerate(self._caches):
            value = await cache.get(key)
            if value is not None:
                # Promote to earlier caches with consistent TTL
                for earlier_cache in self._caches[:i]:
                    await earlier_cache.set(key, value, ttl=ttl)
                return value
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set a value in all caches.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds
        """
        for cache in self._caches:
            await cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete a value from all caches.

        Args:
            key: The cache key

        Returns:
            True if the key existed in any cache
        """
        deleted = False
        for cache in self._caches:
            if await cache.delete(key):
                deleted = True
        return deleted

    async def exists(self, key: str) -> bool:
        """Check if a key exists in any cache.

        Args:
            key: The cache key

        Returns:
            True if the key exists in any cache
        """
        for cache in self._caches:
            if await cache.exists(key):
                return True
        return False

    async def clear(self) -> None:
        """Clear all entries from all caches."""
        for cache in self._caches:
            await cache.clear()

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern from all caches.

        Args:
            pattern: The pattern to match

        Returns:
            Maximum number of keys deleted from any single cache
        """
        max_deleted = 0
        for cache in self._caches:
            try:
                deleted = await cache.delete_pattern(pattern)
                max_deleted = max(max_deleted, deleted)
            except NotImplementedError:
                continue
        return max_deleted

    def stats(self) -> dict:
        """Get statistics from all cache tiers.

        Returns:
            Dictionary with statistics from each tier
        """
        return {
            "tiers": [
                {
                    "type": cache.__class__.__name__,
                    **(cache.stats() if hasattr(cache, "stats") else {}),
                }
                for cache in self._caches
            ]
        }
