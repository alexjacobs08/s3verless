"""Cache key generation utilities for S3verless."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Type
from uuid import UUID

from s3verless.core.base import BaseS3Model


def _json_serializer(obj: Any) -> str:
    """Custom JSON serializer for cache key generation."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return str(obj)
    elif hasattr(obj, "__dict__"):
        return str(obj.__dict__)
    return str(obj)


class CacheKeyBuilder:
    """Utility class for building consistent cache keys.

    This class provides methods for generating cache keys that are:
    - Consistent across requests
    - Human-readable for debugging
    - Safe for all cache backends
    """

    def __init__(self, prefix: str = "s3v"):
        """Initialize the key builder.

        Args:
            prefix: Global prefix for all cache keys
        """
        self.prefix = prefix

    def model_key(
        self,
        model_class: Type[BaseS3Model],
        object_id: str,
    ) -> str:
        """Generate a cache key for a single model instance.

        Args:
            model_class: The model class
            object_id: The object ID

        Returns:
            Cache key like "s3v:model:Product:abc123"
        """
        return f"{self.prefix}:model:{model_class.__name__}:{object_id}"

    def model_list_key(
        self,
        model_class: Type[BaseS3Model],
        filters: dict[str, Any] | None = None,
        sort_field: str | None = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """Generate a cache key for a list query.

        Args:
            model_class: The model class
            filters: Query filters
            sort_field: Sort field
            sort_order: Sort order
            page: Page number
            page_size: Page size

        Returns:
            Cache key that uniquely identifies the query
        """
        # Create a deterministic hash of the query parameters
        query_parts = {
            "filters": filters or {},
            "sort_field": sort_field,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
        }

        # Use custom serializer to handle non-JSON types in filters
        query_str = json.dumps(query_parts, sort_keys=True, default=_json_serializer)
        # Use SHA256 for better collision resistance (full hash)
        query_hash = hashlib.sha256(query_str.encode()).hexdigest()[:16]

        return f"{self.prefix}:list:{model_class.__name__}:{query_hash}"

    def model_count_key(
        self,
        model_class: Type[BaseS3Model],
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Generate a cache key for a count query.

        Args:
            model_class: The model class
            filters: Query filters

        Returns:
            Cache key for the count query
        """
        if filters:
            # Use custom serializer to handle non-JSON types
            filter_str = json.dumps(filters, sort_keys=True, default=_json_serializer)
            # Use SHA256 for better collision resistance
            filter_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:16]
            return f"{self.prefix}:count:{model_class.__name__}:{filter_hash}"
        return f"{self.prefix}:count:{model_class.__name__}:all"

    def model_pattern(self, model_class: Type[BaseS3Model]) -> str:
        """Generate a pattern matching all keys for a model.

        Useful for invalidating all cached data for a model.

        Args:
            model_class: The model class

        Returns:
            Pattern like "s3v:*:Product:*"
        """
        return f"{self.prefix}:*:{model_class.__name__}:*"

    def model_instance_pattern(self, model_class: Type[BaseS3Model]) -> str:
        """Generate a pattern matching all instance keys for a model.

        Args:
            model_class: The model class

        Returns:
            Pattern like "s3v:model:Product:*"
        """
        return f"{self.prefix}:model:{model_class.__name__}:*"

    def model_list_pattern(self, model_class: Type[BaseS3Model]) -> str:
        """Generate a pattern matching all list keys for a model.

        Args:
            model_class: The model class

        Returns:
            Pattern like "s3v:list:Product:*"
        """
        return f"{self.prefix}:list:{model_class.__name__}:*"

    def custom_key(self, *parts: str) -> str:
        """Generate a custom cache key.

        Args:
            *parts: Key parts to join

        Returns:
            Cache key with parts joined by ':'
        """
        return f"{self.prefix}:" + ":".join(parts)


# Default key builder instance
_key_builder: CacheKeyBuilder | None = None


def get_key_builder() -> CacheKeyBuilder:
    """Get the default cache key builder.

    Returns:
        The CacheKeyBuilder instance
    """
    global _key_builder
    if _key_builder is None:
        _key_builder = CacheKeyBuilder()
    return _key_builder


def set_key_builder(builder: CacheKeyBuilder) -> None:
    """Set the default cache key builder.

    Args:
        builder: The CacheKeyBuilder instance to use
    """
    global _key_builder
    _key_builder = builder
