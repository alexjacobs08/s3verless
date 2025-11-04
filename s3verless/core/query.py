"""Query builder for S3-stored objects."""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from s3verless.core.base import BaseS3Model
from s3verless.core.client import S3ClientProtocol
from s3verless.core.exceptions import S3verlessException

T = TypeVar("T", bound=BaseS3Model)


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class FilterOperator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


@dataclass
class Filter:
    """Represents a single filter condition."""

    field: str
    operator: FilterOperator
    value: Any

    def matches(self, obj: dict[str, Any]) -> bool:
        """Check if an object matches this filter."""
        field_value = obj.get(self.field)

        if self.operator == FilterOperator.EQ:
            return field_value == self.value
        elif self.operator == FilterOperator.NEQ:
            return field_value != self.value
        elif self.operator == FilterOperator.GT:
            return field_value > self.value if field_value is not None else False
        elif self.operator == FilterOperator.GTE:
            return field_value >= self.value if field_value is not None else False
        elif self.operator == FilterOperator.LT:
            return field_value < self.value if field_value is not None else False
        elif self.operator == FilterOperator.LTE:
            return field_value <= self.value if field_value is not None else False
        elif self.operator == FilterOperator.IN:
            return (
                field_value in self.value
                if isinstance(self.value, (list, tuple))
                else False
            )
        elif self.operator == FilterOperator.NOT_IN:
            return (
                field_value not in self.value
                if isinstance(self.value, (list, tuple))
                else True
            )
        elif self.operator == FilterOperator.CONTAINS:
            return (
                str(self.value) in str(field_value)
                if field_value is not None
                else False
            )
        elif self.operator == FilterOperator.STARTS_WITH:
            return (
                str(field_value).startswith(str(self.value))
                if field_value is not None
                else False
            )
        elif self.operator == FilterOperator.ENDS_WITH:
            return (
                str(field_value).endswith(str(self.value))
                if field_value is not None
                else False
            )
        elif self.operator == FilterOperator.IS_NULL:
            return field_value is None
        elif self.operator == FilterOperator.IS_NOT_NULL:
            return field_value is not None
        else:
            return False


@dataclass
class QueryResult(Generic[T]):
    """Result of a query operation."""

    items: list[T]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
    continuation_token: str | None = None


class S3Query(Generic[T]):
    """Query builder for S3-stored objects.

    Note: S3 is not a database and doesn't support native querying.
    This implementation fetches objects and filters in memory, which has
    performance implications for large datasets. Consider:
    - Using indexes for frequently queried fields
    - Implementing caching for read-heavy workloads
    - Paginating results to avoid loading all data at once
    """

    def __init__(
        self, model_class: type[T], s3_client: S3ClientProtocol, bucket_name: str
    ):
        self.model_class = model_class
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self._filters: list[Filter] = []
        self._sort_field: str | None = None
        self._sort_order: SortOrder = SortOrder.ASC
        self._limit: int | None = None
        self._offset: int = 0
        self._select_fields: list[str] | None = None
        self._prefetch_related: list[str] = []

    def filter(self, **kwargs) -> "S3Query[T]":
        """Add filter conditions using kwargs syntax.

        Examples:
            .filter(name="John")
            .filter(age__gt=18)
            .filter(email__contains="@example.com")
        """
        for key, value in kwargs.items():
            if "__" in key:
                field, op = key.rsplit("__", 1)
                operator = self._parse_operator(op)
            else:
                field = key
                operator = FilterOperator.EQ

            self._filters.append(Filter(field, operator, value))
        return self

    def _parse_operator(self, op: str) -> FilterOperator:
        """Parse string operator to FilterOperator enum."""
        mapping = {
            "eq": FilterOperator.EQ,
            "neq": FilterOperator.NEQ,
            "gt": FilterOperator.GT,
            "gte": FilterOperator.GTE,
            "lt": FilterOperator.LT,
            "lte": FilterOperator.LTE,
            "in": FilterOperator.IN,
            "not_in": FilterOperator.NOT_IN,
            "contains": FilterOperator.CONTAINS,
            "starts_with": FilterOperator.STARTS_WITH,
            "ends_with": FilterOperator.ENDS_WITH,
            "is_null": FilterOperator.IS_NULL,
            "is_not_null": FilterOperator.IS_NOT_NULL,
        }
        return mapping.get(op, FilterOperator.EQ)

    def exclude(self, **kwargs) -> "S3Query[T]":
        """Add exclusion filters."""
        for key, value in kwargs.items():
            if "__" in key:
                field, _ = key.rsplit("__", 1)
            else:
                field = key
            self._filters.append(Filter(field, FilterOperator.NEQ, value))
        return self

    def order_by(self, field: str) -> "S3Query[T]":
        """Order results by field. Use '-field' for descending order."""
        if field.startswith("-"):
            self._sort_field = field[1:]
            self._sort_order = SortOrder.DESC
        else:
            self._sort_field = field
            self._sort_order = SortOrder.ASC
        return self

    def limit(self, n: int) -> "S3Query[T]":
        """Limit the number of results."""
        self._limit = n
        return self

    def offset(self, n: int) -> "S3Query[T]":
        """Skip n results."""
        self._offset = n
        return self

    def select(self, *fields: str) -> "S3Query[T]":
        """Select only specific fields."""
        self._select_fields = list(fields)
        return self

    def prefetch_related(self, *relations: str) -> "S3Query[T]":
        """Prefetch related objects to avoid N+1 queries."""
        self._prefetch_related.extend(relations)
        return self

    async def count(self) -> int:
        """Count matching objects without fetching them."""
        # For now, we need to list all objects
        # As a future improvement, we might maintain counters in S3
        objects = await self._list_all_objects()
        return len(objects)

    async def exists(self) -> bool:
        """Check if any matching objects exist."""
        objects = await self._list_all_objects()
        return len(objects) > 0

    async def first(self) -> T | None:
        """Get the first matching object."""
        self._limit = 1
        results = await self.all()
        return results[0] if results else None

    async def get(self, **kwargs) -> T:
        """Get a single object matching the filters."""
        self.filter(**kwargs)
        results = await self.all()
        if len(results) == 0:
            raise S3verlessException(
                f"No {self.model_class.__name__} found matching filters"
            )
        if len(results) > 1:
            raise S3verlessException(
                f"Multiple {self.model_class.__name__} found matching filters"
            )
        return results[0]

    async def all(self) -> list[T]:
        """Execute the query and return all results.

        Note: This loads objects into memory for filtering and sorting.
        For large datasets, consider using pagination or limiting results.
        """
        objects = await self._list_all_objects()

        # Apply sorting
        if self._sort_field:
            reverse = self._sort_order == SortOrder.DESC
            objects.sort(key=lambda x: x.get(self._sort_field, ""), reverse=reverse)

        # Apply offset and limit
        if self._offset:
            objects = objects[self._offset :]
        if self._limit:
            objects = objects[: self._limit]

        # Convert to model instances
        results = []
        for obj in objects:
            if self._select_fields:
                # Filter fields if select() was used
                obj = {k: v for k, v in obj.items() if k in self._select_fields}
            results.append(self.model_class(**obj))

        # Handle prefetch_related
        if self._prefetch_related:
            await self._do_prefetch(results)

        return results

    async def paginate(self, page: int = 1, page_size: int = 20) -> QueryResult[T]:
        """Get paginated results."""
        # Get total count BEFORE setting limit/offset
        total_count = await self.count()

        # Now set pagination parameters
        self._offset = (page - 1) * page_size
        self._limit = page_size

        # Get items for current page
        items = await self.all()

        return QueryResult(
            items=items,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total_count,
            has_prev=page > 1,
        )

    async def _list_all_objects(self) -> list[dict[str, Any]]:
        """List all objects matching the filters from S3.

        This method fetches objects in batches and applies filters.
        Performance optimization: Early termination when limit + offset is reached
        during listing (before sorting).

        Returns:
            List of dictionaries representing matching objects
        """
        prefix = self.model_class.get_s3_prefix()

        objects: list[dict[str, Any]] = []
        continuation_token: str | None = None

        # Calculate early termination threshold
        # If we have a limit without sorting, we can stop early
        max_needed = None
        if self._limit is not None and not self._sort_field:
            max_needed = self._limit + self._offset

        while True:
            # List objects with prefix
            params: dict[str, Any] = {
                "Bucket": self.bucket_name,
                "Prefix": prefix,
                "MaxKeys": 1000,
            }
            if continuation_token:
                params["ContinuationToken"] = continuation_token

            response = await self.s3_client.list_objects_v2(**params)

            if "Contents" not in response:
                break

            # Process objects in batch for better performance
            fetch_tasks = []
            for obj_summary in response["Contents"]:
                key = obj_summary["Key"]

                # Skip non-JSON files
                if not key.endswith(".json"):
                    continue

                # Create async task to fetch object
                fetch_tasks.append(self._fetch_and_filter_object(key))

            # Fetch all objects in this batch concurrently
            batch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            # Collect successful results
            for result in batch_results:
                if isinstance(result, dict):
                    objects.append(result)

                    # Early termination if we have enough objects
                    if max_needed and len(objects) >= max_needed:
                        return objects

            # Check if there are more objects
            if not response.get("IsTruncated", False):
                break

            continuation_token = response.get("NextContinuationToken")

        return objects

    async def _fetch_and_filter_object(self, key: str) -> dict[str, Any] | None:
        """Fetch an object from S3 and apply filters.

        Args:
            key: S3 object key

        Returns:
            Object data if it matches filters, None otherwise
        """
        try:
            # Get object
            obj_response = await self.s3_client.get_object(
                Bucket=self.bucket_name, Key=key
            )
            content = await obj_response["Body"].read()
            obj_data = json.loads(content)

            # Apply filters
            if self._matches_filters(obj_data):
                return obj_data
            return None
        except Exception:
            # Skip objects that can't be loaded or parsed
            return None

    def _matches_filters(self, obj: dict[str, Any]) -> bool:
        """Check if an object matches all filters."""
        for f in self._filters:
            if not f.matches(obj):
                return False
        return True

    async def _do_prefetch(self, items: list[T]) -> None:
        """Prefetch related objects."""
        # This would be implemented based on relationship definitions
        # For now, it's a placeholder
        pass

    async def update(self, **kwargs) -> int:
        """Update all matching objects."""
        objects = await self._list_all_objects()
        count = 0

        for obj_data in objects:
            # Update fields
            for key, value in kwargs.items():
                obj_data[key] = value

            # Update timestamp
            obj_data["updated_at"] = datetime.now().isoformat()

            # Save back to S3
            obj_id = obj_data["id"]
            key = self.model_class.get_s3_key(obj_id)

            await self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(obj_data),
                ContentType="application/json",
            )
            count += 1

        return count

    async def delete(self) -> int:
        """Delete all matching objects."""
        objects = await self._list_all_objects()
        count = 0

        for obj_data in objects:
            obj_id = obj_data["id"]
            key = self.model_class.get_s3_key(obj_id)

            await self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            count += 1

        return count


def query(
    model_class: type[T], s3_client: S3ClientProtocol, bucket_name: str
) -> S3Query[T]:
    """Create a query for a model class.

    Args:
        model_class: The model class to query
        s3_client: S3 client instance
        bucket_name: S3 bucket name

    Returns:
        S3Query instance for building and executing queries

    Example:
        >>> from s3verless import query, BaseS3Model
        >>> class Product(BaseS3Model):
        ...     name: str
        ...     price: float
        >>>
        >>> results = await query(Product, s3_client, "my-bucket").filter(
        ...     price__lt=100
        ... ).order_by("name").limit(10).all()
    """
    return S3Query(model_class, s3_client, bucket_name)
