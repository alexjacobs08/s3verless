"""Base model for S3-stored objects."""

import uuid
from datetime import datetime, timezone
from typing import ClassVar, Type

from pydantic import BaseModel, Field

from s3verless.core.registry import (
    get_model_s3_prefix,
    register_model,
)  # Import registry functions


def aware_now() -> datetime:
    """Return the current time as a timezone-aware datetime object."""
    return datetime.now(timezone.utc)


class BaseS3Model(BaseModel):
    """Base model for objects stored in S3.

    All models that will be stored in S3 should inherit from this class.
    Provides automatic ID generation and timestamps.
    It automatically registers itself with the s3verless registry
    to determine its S3 path based on the configured base path.

    Attributes:
        id: Unique identifier for the object
        created_at: Timestamp when the object was created
        updated_at: Timestamp when the object was last updated

    Class Attributes (optional):
        _plural_name: Override the auto-generated plural name
        _api_prefix: Override the auto-generated API prefix
        _enable_api: Enable/disable automatic API generation (default: True)
        _enable_admin: Enable/disable admin interface (default: True)
        _indexes: List of fields to index for faster queries
        _unique_fields: List of fields that must be unique
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=aware_now)
    updated_at: datetime = Field(default_factory=aware_now)

    # Optional class attributes for configuration
    _plural_name: ClassVar[str] = ""
    _api_prefix: ClassVar[str] = ""
    _enable_api: ClassVar[bool] = True
    _enable_admin: ClassVar[bool] = True
    _indexes: ClassVar[list[str]] = []
    _unique_fields: ClassVar[list[str]] = []

    def __init_subclass__(cls: Type["BaseS3Model"], **kwargs) -> None:
        """Automatically register subclasses with the registry."""
        super().__init_subclass__(**kwargs)
        register_model(cls)

    @classmethod
    def get_s3_prefix(cls) -> str:
        """Get the calculated S3 prefix for this model class from the registry."""
        return get_model_s3_prefix(cls)

    @classmethod
    def get_s3_key(cls, object_id: uuid.UUID | str) -> str:
        """Generate the S3 object key for a given ID using the registered prefix.

        Args:
            object_id: The UUID or string ID of the object

        Returns:
            The full S3 key path for the object

        Raises:
            ValueError: If the base S3 path is not configured in the registry.
        """
        prefix = cls.get_s3_prefix()
        if not prefix:
            # Check if the base path component is missing
            from s3verless.core.registry import get_base_s3_path

            if not get_base_s3_path():
                raise ValueError(
                    f"Base S3 path not configured. Use s3verless.core.registry.set_base_s3_path() "
                    f"before defining or using {cls.__name__}."
                )
            # Should not happen if base path is set and model is registered, but good failsafe
            raise ValueError(
                f"Could not determine S3 prefix for model {cls.__name__}. Ensure base path is set."
            )

        # Prefix already ends with a slash from get_model_s3_prefix
        return f"{prefix}{object_id}.json"

    def touch(self) -> None:
        """Update the updated_at timestamp to the current time."""
        self.updated_at = aware_now()

    @property
    def s3_key(self) -> str:
        """Get the S3 key for this specific instance."""
        return self.get_s3_key(self.id)

    model_config = {
        "json_encoders": {uuid.UUID: str, datetime: lambda dt: dt.isoformat()}
    }
