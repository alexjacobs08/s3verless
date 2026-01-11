# Caching Guide

Speed up your S3verless application with in-memory caching.

## Overview

S3verless provides caching backends to reduce S3 API calls and improve response times. Since S3 operations have latency, caching frequently accessed data can significantly improve performance.

## Cache Backends

### InMemoryCache

Simple cache with TTL and optional size limits:

```python
from s3verless.cache.memory import InMemoryCache

cache = InMemoryCache(
    default_ttl=300,      # 5 minutes default TTL
    max_size=1000,        # Max entries (None for unlimited)
    cleanup_interval=60,  # Clean expired entries every 60s
)
```

### LRUCache

Least Recently Used eviction with hit rate tracking:

```python
from s3verless.cache.memory import LRUCache

cache = LRUCache(
    max_size=1000,        # Max entries
    default_ttl=300,      # 5 minutes default TTL
)

# Check hit rate
stats = cache.stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
```

### CompositeCache

Multi-tier caching for optimal performance:

```python
from s3verless.cache.composite import CompositeCache

cache = CompositeCache([
    LRUCache(max_size=100, default_ttl=60),     # L1: Fast, small
    InMemoryCache(max_size=1000, default_ttl=300),  # L2: Larger
])
```

On cache miss, later tiers are checked and hits are promoted to earlier tiers.

## Basic Usage

```python
# Set a value
await cache.set("product:123", product_data, ttl=300)

# Get a value
data = await cache.get("product:123")
if data is None:
    # Cache miss - fetch from S3
    data = await fetch_from_s3()
    await cache.set("product:123", data)

# Check existence
exists = await cache.exists("product:123")

# Delete a value
await cache.delete("product:123")

# Delete by pattern
await cache.delete_pattern("product:*")

# Clear all
await cache.clear()
```

## Cache Key Builder

Generate consistent cache keys:

```python
from s3verless.cache.keys import CacheKeyBuilder

keys = CacheKeyBuilder(prefix="myapp")

# Model instance key
key = keys.model_key(Product, "abc123")
# "myapp:model:Product:abc123"

# List query key
key = keys.model_list_key(
    Product,
    filters={"category": "electronics"},
    sort_field="price",
    page=1,
)
# "myapp:list:Product:a1b2c3d4..."  (hash of query params)

# Count query key
key = keys.model_count_key(Product, filters={"active": True})
# "myapp:count:Product:e5f6g7h8..."

# Pattern for invalidation
pattern = keys.model_pattern(Product)
# "myapp:*:Product:*"
```

## Caching Patterns

### Cache-Aside Pattern

```python
async def get_product(product_id: str) -> Product:
    cache_key = f"product:{product_id}"

    # Try cache first
    cached = await cache.get(cache_key)
    if cached:
        return Product(**cached)

    # Fetch from S3
    product = await product_service.get(s3_client, UUID(product_id))
    if product:
        await cache.set(cache_key, product.model_dump(), ttl=300)

    return product
```

### Write-Through Pattern

```python
async def update_product(product_id: str, data: dict) -> Product:
    # Update in S3
    product = await product_service.update(s3_client, UUID(product_id), data)

    # Update cache
    cache_key = f"product:{product_id}"
    await cache.set(cache_key, product.model_dump(), ttl=300)

    # Invalidate list caches
    await cache.delete_pattern("product:list:*")

    return product
```

### Cache Invalidation

```python
async def invalidate_product_cache(product_id: str):
    # Delete specific product
    await cache.delete(f"product:{product_id}")

    # Delete all list/count caches for Product
    await cache.delete_pattern("product:list:*")
    await cache.delete_pattern("product:count:*")
```

## Integration with Query

```python
from s3verless.cache.keys import CacheKeyBuilder

keys = CacheKeyBuilder()

async def cached_query(
    filters: dict = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    cache_key = keys.model_list_key(
        Product, filters=filters, page=page, page_size=page_size
    )

    cached = await cache.get(cache_key)
    if cached:
        return cached

    query = Query(Product, s3_client, bucket)
    if filters:
        query = query.filter(**filters)

    result = await query.paginate(page, page_size)

    # Cache the result
    result_dict = {
        "items": [item.model_dump() for item in result.items],
        "total_count": result.total_count,
        "page": result.page,
        "has_next": result.has_next,
    }
    await cache.set(cache_key, result_dict, ttl=60)

    return result_dict
```

## FastAPI Middleware

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cache: CacheBackend):
        super().__init__(app)
        self.cache = cache

    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Generate cache key from URL
        cache_key = f"response:{request.url.path}:{request.url.query}"

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            return JSONResponse(cached)

        # Get response
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            data = json.loads(body)
            await self.cache.set(cache_key, data, ttl=60)
            return JSONResponse(data)

        return response
```

## Cache Statistics

```python
# InMemoryCache stats
stats = cache.stats()
# {"size": 150, "max_size": 1000, "default_ttl": 300}

# LRUCache stats with hit rate
stats = cache.stats()
# {"size": 150, "max_size": 1000, "hits": 1000, "misses": 200, "hit_rate": 0.83}

# CompositeCache stats
stats = cache.stats()
# {"tiers": [{"type": "LRUCache", ...}, {"type": "InMemoryCache", ...}]}
```

## Best Practices

1. **Set appropriate TTLs** - Balance freshness vs. performance
2. **Invalidate on writes** - Keep cache consistent with S3
3. **Use patterns for bulk invalidation** - When data relationships exist
4. **Monitor hit rates** - Adjust cache size/TTL based on metrics
5. **Size limits** - Prevent memory exhaustion with max_size
6. **Tiered caching** - Small fast L1, larger L2 for different access patterns
7. **Cache serializable data** - Use model_dump() for Pydantic models

## When to Cache

Good candidates:
- Frequently accessed read data
- Expensive queries (filters, sorts, aggregations)
- Reference data (categories, configurations)
- User session data

Avoid caching:
- Write-heavy data
- Large objects
- Sensitive data without encryption
- Data that must be real-time
