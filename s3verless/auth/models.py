"""Authentication models for S3verless."""

from typing import ClassVar

from pydantic import EmailStr, Field

from s3verless.core.base import BaseS3Model


class S3User(BaseS3Model):
    """Base user model for S3verless authentication.

    This model provides the basic fields needed for user authentication.
    It can be extended with additional fields as needed.

    Note: This model is excluded from the API and admin interface by default
    since users should ONLY be created through the authentication service
    which handles password hashing and validation properly.

    Security: Direct CRUD access to S3User would expose hashed passwords
    and bypass password validation. Always use S3AuthService methods.
    """

    s3_prefix: ClassVar[str] = "users"  # Default prefix for user objects
    _enable_api: ClassVar[bool] = False  # No auto-generated CRUD endpoints
    _enable_admin: ClassVar[bool] = False  # Don't show in admin interface

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    hashed_password: str
    full_name: str | None = None
    is_active: bool = True
    is_admin: bool = False  # Admin users can bypass ownership checks

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "is_active": True,
            }
        }
    }
