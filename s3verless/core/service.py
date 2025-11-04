"""Core service for S3 data operations."""

import json
import uuid
from typing import Generic, Type, TypeVar

from aiobotocore.client import AioBaseClient
from botocore.exceptions import ClientError
from pydantic import BaseModel

from s3verless.core.base import BaseS3Model
from s3verless.core.exceptions import S3ModelError, S3OperationError
from s3verless.core.registry import get_model_metadata

# Generic TypeVar for models that inherit from BaseS3Model
T = TypeVar("T", bound=BaseS3Model)


class S3DataService(Generic[T]):
    """Service layer for CRUD operations on Pydantic models stored in S3.

    Uses the s3verless registry to determine the S3 prefix for models.

    Type Parameters:
        T: A Pydantic model type that inherits from BaseS3Model
    """

    def __init__(self, model: Type[T], bucket_name: str):
        """Initialize the service.

        Args:
            model: The Pydantic model class to handle
            bucket_name: The S3 bucket name
        """
        self.model = model
        self.bucket_name = bucket_name

    @property
    def s3_prefix(self) -> str:
        """Get the S3 prefix for the associated model."""
        return self.model.get_s3_prefix()

    async def get(self, s3_client: AioBaseClient, obj_id: uuid.UUID) -> T | None:
        """Retrieve a single object from S3 by its ID.

        Args:
            s3_client: The S3 client to use
            obj_id: The UUID of the object to retrieve

        Returns:
            The model instance if found, None otherwise

        Raises:
            S3OperationError: If the S3 operation fails
            ValueError: If base S3 path is not configured
        """
        key = self.model.get_s3_key(obj_id)
        try:
            response = await s3_client.get_object(Bucket=self.bucket_name, Key=key)
            body = await response["Body"].read()
            data = json.loads(body.decode("utf-8"))
            return self.model.model_validate(data)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise S3OperationError(f"Failed to get object {key}: {e}")
        except Exception as e:
            raise S3OperationError(f"Unexpected error getting object {key}: {e}")

    async def create(self, s3_client: AioBaseClient, data: BaseModel) -> T:
        """Create a new object in S3.

        Args:
            s3_client: The S3 client to use
            data: The data to create the object from

        Returns:
            The created model instance

        Raises:
            S3OperationError: If the S3 operation fails
            S3ModelError: If unique field validation fails
            ValueError: If base S3 path is not configured
        """
        new_obj = self.model(**data.model_dump())

        # Validate unique fields before creating
        await self._validate_unique_fields(s3_client, new_obj)

        key = new_obj.get_s3_key(new_obj.id)

        try:
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=new_obj.model_dump_json().encode("utf-8"),
                ContentType="application/json",
            )
            return new_obj
        except Exception as e:
            raise S3OperationError(f"Failed to create object {key}: {e}")

    async def update(
        self, s3_client: AioBaseClient, obj_id: uuid.UUID, update_data: BaseModel
    ) -> T | None:
        """Update an existing object in S3.

        Args:
            s3_client: The S3 client to use
            obj_id: The UUID of the object to update
            update_data: The new data to update with

        Returns:
            The updated model instance if found, None otherwise

        Raises:
            S3OperationError: If the S3 operation fails
            S3ModelError: If unique field validation fails
            ValueError: If base S3 path is not configured
        """
        existing_obj = await self.get(s3_client, obj_id)
        if not existing_obj:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        updated_obj = existing_obj.model_copy(update=update_dict)
        updated_obj.touch()

        # Validate unique fields before updating (excluding current object)
        await self._validate_unique_fields(s3_client, updated_obj, exclude_id=obj_id)

        key = updated_obj.get_s3_key(updated_obj.id)
        try:
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=updated_obj.model_dump_json().encode("utf-8"),
                ContentType="application/json",
            )
            return updated_obj
        except Exception as e:
            raise S3OperationError(f"Failed to update object {key}: {e}")

    async def delete(self, s3_client: AioBaseClient, obj_id: uuid.UUID) -> bool:
        """Delete an object from S3.

        Args:
            s3_client: The S3 client to use
            obj_id: The UUID of the object to delete

        Returns:
            True if deleted, False if not found

        Raises:
            S3OperationError: If the S3 operation fails
            ValueError: If base S3 path is not configured
        """
        key = self.model.get_s3_key(obj_id)
        try:
            await s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ["NoSuchKey", "404"]:
                return False
            raise S3OperationError(f"Failed to delete object {key}: {e}")
        except Exception as e:
            raise S3OperationError(f"Unexpected error deleting object {key}: {e}")

    async def exists(self, s3_client: AioBaseClient, obj_id: uuid.UUID) -> bool:
        """Check if an object exists in S3.

        Args:
            s3_client: The S3 client to use
            obj_id: The UUID of the object to check

        Returns:
            True if the object exists, False otherwise

        Raises:
            S3OperationError: If the S3 operation fails
        """
        key = self.model.get_s3_key(obj_id)
        try:
            await s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ["NoSuchKey", "404", "NotFound"]:
                return False
            raise S3OperationError(f"Failed to check object {key}: {e}")
        except Exception as e:
            raise S3OperationError(f"Unexpected error checking object {key}: {e}")

    async def list_by_prefix(
        self, s3_client: AioBaseClient, limit: int = 100, marker: str | None = None
    ) -> tuple[list[T], str | None]:
        """List objects in S3 under the model's dynamically determined prefix.

        Args:
            s3_client: The S3 client to use
            limit: Maximum number of objects to return
            marker: Pagination marker from previous request

        Returns:
            Tuple of (list of objects, next marker if more results exist)

        Raises:
            S3OperationError: If the S3 operation fails
            ValueError: If base S3 path is not configured
        """
        objects = []
        next_marker = None
        current_prefix = self.s3_prefix

        try:
            list_kwargs = {
                "Bucket": self.bucket_name,
                "Prefix": current_prefix,
                "MaxKeys": limit,
            }
            if marker:
                list_kwargs["Marker"] = marker

            response = await s3_client.list_objects_v2(**list_kwargs)

            if "Contents" in response:
                for item in response["Contents"]:
                    key = item["Key"]
                    if (
                        key.startswith(current_prefix)
                        and key.endswith(".json")
                        and "/" not in key[len(current_prefix) :]
                    ):
                        try:
                            obj_id_str = key[len(current_prefix) : -len(".json")]
                            obj_id = uuid.UUID(obj_id_str)
                            obj = await self.get(s3_client, obj_id)
                            if obj:
                                objects.append(obj)
                        except (ValueError, IndexError):
                            continue

            if response.get("IsTruncated"):
                next_marker = (
                    response.get("NextContinuationToken")
                    or response["Contents"][-1]["Key"]
                    if response.get("Contents")
                    else None
                )

            return objects, next_marker

        except Exception as e:
            raise S3OperationError(
                f"Failed to list objects with prefix {current_prefix}: {e}"
            )

    async def paginate(
        self, s3_client: AioBaseClient, page: int = 1, page_size: int = 20
    ) -> dict:
        """List objects with pagination support.

        Args:
            s3_client: The S3 client to use
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Dict with pagination information:
            - items: List of objects for current page
            - total_count: Total number of objects
            - page: Current page number
            - page_size: Items per page
            - has_next: Whether there's a next page
            - has_prev: Whether there's a previous page

        Raises:
            S3OperationError: If the S3 operation fails
        """
        # Get all objects (in production, this should be optimized)
        all_objects = []
        marker = None

        while True:
            objects, marker = await self.list_by_prefix(
                s3_client, limit=1000, marker=marker
            )
            all_objects.extend(objects)
            if not marker:
                break

        # Calculate pagination
        total_count = len(all_objects)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        items = all_objects[start_idx:end_idx]

        return {
            "items": items,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_next": end_idx < total_count,
            "has_prev": page > 1,
        }

    async def _validate_unique_fields(
        self, s3_client: AioBaseClient, obj: T, exclude_id: uuid.UUID | None = None
    ) -> None:
        """Validate that unique field constraints are not violated.

        Args:
            s3_client: The S3 client to use
            obj: The object to validate
            exclude_id: Optional ID to exclude from uniqueness check (for updates)

        Raises:
            S3ModelError: If a unique field constraint is violated
        """
        # Get model metadata to check for unique fields
        metadata = get_model_metadata(self.model.__name__)
        if not metadata or not metadata.unique_fields:
            return  # No unique fields defined

        # List all existing objects
        all_objects: list[T] = []
        marker = None

        while True:
            objects, marker = await self.list_by_prefix(
                s3_client, limit=1000, marker=marker
            )
            all_objects.extend(objects)
            if not marker:
                break

        # Check each unique field
        obj_dict = obj.model_dump()
        for field_name in metadata.unique_fields:
            if field_name not in obj_dict:
                continue

            field_value = obj_dict[field_name]

            # Check if any other object has the same value for this field
            for existing_obj in all_objects:
                # Skip the object itself during updates
                if exclude_id and existing_obj.id == exclude_id:
                    continue

                existing_dict = existing_obj.model_dump()
                if existing_dict.get(field_name) == field_value:
                    raise S3ModelError(
                        f"Unique constraint violation: {field_name}='{field_value}' already exists"
                    )
