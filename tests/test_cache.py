"""Tests for cache module."""

import pytest
import asyncio
from typing import ClassVar

from s3verless.cache.memory import InMemoryCache, LRUCache
from s3verless.cache.composite import CompositeCache
from s3verless.cache.keys import CacheKeyBuilder
from s3verless.core.base import BaseS3Model


class CacheTestModel(BaseS3Model):
    """Test model for cache key tests."""

    _plural_name: ClassVar[str] = "cache_test_models"

    name: str


class TestInMemoryCache:
    """Tests for InMemoryCache."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test basic set and get."""
        cache = InMemoryCache()

        await cache.set("key1", {"value": 123})
        result = await cache.get("key1")

        assert result == {"value": 123}

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting a nonexistent key."""
        cache = InMemoryCache()

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a key."""
        cache = InMemoryCache()

        await cache.set("key1", "value1")
        await cache.delete("key1")
        result = await cache.get("key1")

        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing all keys."""
        cache = InMemoryCache()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = InMemoryCache(default_ttl=1)  # 1 second TTL

        await cache.set("key1", "value1")

        # Should exist immediately
        assert await cache.get("key1") == "value1"

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """Test custom TTL per key."""
        cache = InMemoryCache(default_ttl=60)

        await cache.set("key1", "value1", ttl=1)

        # Wait for expiration
        await asyncio.sleep(1.5)

        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_exists(self):
        """Test exists method."""
        cache = InMemoryCache()

        await cache.set("key1", "value1")

        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_stats(self):
        """Test cache statistics."""
        cache = InMemoryCache(default_ttl=300, max_size=100)

        await cache.set("key1", "value1")

        stats = cache.stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["default_ttl"] == 300

    @pytest.mark.asyncio
    async def test_delete_pattern(self):
        """Test deleting keys by pattern."""
        cache = InMemoryCache()

        await cache.set("user:1", "data1")
        await cache.set("user:2", "data2")
        await cache.set("other:1", "data3")

        deleted = await cache.delete_pattern("user:*")

        assert deleted == 2
        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
        assert await cache.get("other:1") == "data3"

    @pytest.mark.asyncio
    async def test_max_size_eviction(self):
        """Test eviction when max size is reached."""
        cache = InMemoryCache(max_size=2)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")  # Should evict key1

        assert cache.size == 2
        assert await cache.get("key1") is None  # Evicted
        assert await cache.get("key3") == "value3"


class TestLRUCache:
    """Tests for LRUCache."""

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when max size reached."""
        cache = LRUCache(max_size=3)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # Access key1 to make it recently used
        await cache.get("key1")

        # Add key4, should evict key2 (least recently used)
        await cache.set("key4", "value4")

        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_lru_update_access_order(self):
        """Test that getting a key updates its access order."""
        cache = LRUCache(max_size=2)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Access key1 to make it recently used
        await cache.get("key1")

        # Add key3, should evict key2
        await cache.set("key3", "value3")

        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_stats_with_hits_misses(self):
        """Test LRU cache stats with hit/miss tracking."""
        cache = LRUCache(max_size=10)

        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("nonexistent")  # Miss

        stats = cache.stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1


class TestCompositeCache:
    """Tests for CompositeCache."""

    @pytest.mark.asyncio
    async def test_get_from_first_cache(self):
        """Test getting from first available cache."""
        l1 = InMemoryCache()
        l2 = InMemoryCache()
        composite = CompositeCache([l1, l2])

        await l1.set("key1", "value1")

        result = await composite.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_promotes_to_earlier_cache(self):
        """Test that getting from L2 promotes to L1."""
        l1 = InMemoryCache()
        l2 = InMemoryCache()
        composite = CompositeCache([l1, l2])

        # Only set in L2
        await l2.set("key1", "value1")

        # Get should find in L2 and promote to L1
        result = await composite.get("key1")
        assert result == "value1"

        # Now should be in L1
        assert await l1.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_set_writes_to_all_caches(self):
        """Test that set writes to all cache layers."""
        l1 = InMemoryCache()
        l2 = InMemoryCache()
        composite = CompositeCache([l1, l2])

        await composite.set("key1", "value1")

        assert await l1.get("key1") == "value1"
        assert await l2.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_delete_removes_from_all_caches(self):
        """Test that delete removes from all cache layers."""
        l1 = InMemoryCache()
        l2 = InMemoryCache()
        composite = CompositeCache([l1, l2])

        await composite.set("key1", "value1")
        await composite.delete("key1")

        assert await l1.get("key1") is None
        assert await l2.get("key1") is None

    @pytest.mark.asyncio
    async def test_clear_clears_all_caches(self):
        """Test that clear clears all cache layers."""
        l1 = InMemoryCache()
        l2 = InMemoryCache()
        composite = CompositeCache([l1, l2])

        await composite.set("key1", "value1")
        await composite.clear()

        assert await l1.get("key1") is None
        assert await l2.get("key1") is None


class TestCacheKeyBuilder:
    """Tests for CacheKeyBuilder."""

    def test_model_key(self):
        """Test generating key for model instance."""
        builder = CacheKeyBuilder()

        key = builder.model_key(CacheTestModel, "123-456")

        assert key == "s3v:model:CacheTestModel:123-456"

    def test_model_key_custom_prefix(self):
        """Test custom prefix in key builder."""
        builder = CacheKeyBuilder(prefix="myapp")

        key = builder.model_key(CacheTestModel, "123-456")

        assert key.startswith("myapp:")

    def test_model_list_key(self):
        """Test generating key for list query."""
        builder = CacheKeyBuilder()

        key = builder.model_list_key(
            CacheTestModel,
            filters={"is_active": True},
            sort_field="created_at",
            page=1,
            page_size=10
        )

        assert key.startswith("s3v:list:CacheTestModel:")
        assert len(key) > len("s3v:list:CacheTestModel:")

    def test_model_list_key_same_params_same_key(self):
        """Test that same query params produce same key."""
        builder = CacheKeyBuilder()

        key1 = builder.model_list_key(CacheTestModel, {"status": "active"}, "name", "asc", 1, 10)
        key2 = builder.model_list_key(CacheTestModel, {"status": "active"}, "name", "asc", 1, 10)

        assert key1 == key2

    def test_model_list_key_different_params_different_key(self):
        """Test that different query params produce different key."""
        builder = CacheKeyBuilder()

        key1 = builder.model_list_key(CacheTestModel, {"status": "active"})
        key2 = builder.model_list_key(CacheTestModel, {"status": "inactive"})

        assert key1 != key2

    def test_model_pattern(self):
        """Test generating invalidation pattern."""
        builder = CacheKeyBuilder()

        pattern = builder.model_pattern(CacheTestModel)

        assert pattern == "s3v:*:CacheTestModel:*"

    def test_model_instance_pattern(self):
        """Test model instance pattern."""
        builder = CacheKeyBuilder()

        pattern = builder.model_instance_pattern(CacheTestModel)

        assert pattern == "s3v:model:CacheTestModel:*"

    def test_model_list_pattern(self):
        """Test model list pattern."""
        builder = CacheKeyBuilder()

        pattern = builder.model_list_pattern(CacheTestModel)

        assert pattern == "s3v:list:CacheTestModel:*"

    def test_custom_key(self):
        """Test custom key generation."""
        builder = CacheKeyBuilder()

        key = builder.custom_key("user", "123", "profile")

        assert key == "s3v:user:123:profile"
