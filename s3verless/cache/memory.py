"""In-memory cache implementations for S3verless."""

import asyncio
import fnmatch
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from s3verless.cache.base import CacheBackend


@dataclass
class CacheEntry:
    """A single cache entry with optional expiration."""

    value: Any
    expires_at: datetime | None = None

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class InMemoryCache(CacheBackend):
    """Simple in-memory cache with TTL support.

    This cache stores all entries in memory with optional expiration.
    It's suitable for single-process deployments or testing.
    """

    def __init__(
        self,
        default_ttl: int | None = 300,
        max_size: int | None = None,
        cleanup_interval: int = 60,
    ):
        """Initialize the in-memory cache.

        Args:
            default_ttl: Default TTL in seconds (None for no expiration)
            max_size: Maximum number of entries (None for unlimited)
            cleanup_interval: How often to clean expired entries (seconds)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        self._last_cleanup = datetime.now(timezone.utc)

    async def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found/expired
        """
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (None uses default)
        """
        async with self._lock:
            # Use provided TTL or default
            actual_ttl = ttl if ttl is not None else self.default_ttl

            # Calculate expiration
            expires_at = None
            if actual_ttl is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=actual_ttl)

            # Evict if at max size
            if self.max_size and len(self._cache) >= self.max_size:
                # Remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

            # Periodic cleanup
            await self._maybe_cleanup()

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: The cache key

        Returns:
            True if the key existed
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.

        Args:
            key: The cache key

        Returns:
            True if the key exists and is valid
        """
        value = await self.get(key)
        return value is not None

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._cache.clear()

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern.

        Args:
            pattern: The pattern to match (e.g., "model:Product:*")

        Returns:
            Number of keys deleted
        """
        async with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    async def _maybe_cleanup(self) -> None:
        """Periodically clean up expired entries."""
        now = datetime.now(timezone.utc)
        if (now - self._last_cleanup).total_seconds() < self.cleanup_interval:
            return

        self._last_cleanup = now
        keys_to_delete = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in keys_to_delete:
            del self._cache[key]

    @property
    def size(self) -> int:
        """Get the current number of entries in the cache."""
        return len(self._cache)

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
        }


class LRUCache(CacheBackend):
    """Least Recently Used (LRU) cache with TTL support.

    This cache evicts the least recently used entries when it reaches
    max capacity. It's more efficient than InMemoryCache for bounded
    cache sizes.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int | None = 300,
    ):
        """Initialize the LRU cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds (None for no expiration)
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found/expired
        """
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (None uses default)
        """
        async with self._lock:
            # Use provided TTL or default
            actual_ttl = ttl if ttl is not None else self.default_ttl

            # Calculate expiration
            expires_at = None
            if actual_ttl is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=actual_ttl)

            # If key exists, update and move to end
            if key in self._cache:
                self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
                self._cache.move_to_end(key)
            else:
                # Evict LRU entry if at capacity
                while len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)

                self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: The cache key

        Returns:
            True if the key existed
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.

        Args:
            key: The cache key

        Returns:
            True if the key exists and is valid
        """
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                return False
            return True

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern.

        Args:
            pattern: The pattern to match

        Returns:
            Number of keys deleted
        """
        async with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    @property
    def size(self) -> int:
        """Get the current number of entries in the cache."""
        return len(self._cache)

    def stats(self) -> dict:
        """Get cache statistics including hit rate.

        Returns:
            Dictionary with cache statistics
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "default_ttl": self.default_ttl,
        }
