"""Base cache backend interface for S3verless."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

T = TypeVar("T")


class CacheBackend(ABC):
    """Abstract base class for cache backends.

    All cache implementations should inherit from this class and
    implement the required methods.
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found
        """
        pass

    @abstractmethod
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
            ttl: Time-to-live in seconds (None for no expiration)
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: The cache key

        Returns:
            True if the key existed and was deleted
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key

        Returns:
            True if the key exists
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries from the cache."""
        pass

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from the cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary of key -> value for found keys
        """
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_many(
        self,
        mapping: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Set multiple values in the cache.

        Args:
            mapping: Dictionary of key -> value
            ttl: Time-to-live in seconds
        """
        for key, value in mapping.items():
            await self.set(key, value, ttl)

    async def delete_many(self, keys: list[str]) -> int:
        """Delete multiple keys from the cache.

        Args:
            keys: List of cache keys

        Returns:
            Number of keys deleted
        """
        count = 0
        for key in keys:
            if await self.delete(key):
                count += 1
        return count

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Default implementation raises NotImplementedError.
        Subclasses should override if they support pattern matching.

        Args:
            pattern: The pattern to match (e.g., "model:Product:*")

        Returns:
            Number of keys deleted
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support pattern deletion"
        )
