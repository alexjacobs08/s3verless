"""FastAPI integration for S3verless."""

from s3verless.fastapi.auth import (
    S3OAuth2PasswordBearer,
    get_current_active_user,
    get_current_user,
)
from s3verless.fastapi.dependencies import get_s3_client, get_s3_service

__all__ = [
    "S3OAuth2PasswordBearer",
    "get_current_active_user",
    "get_current_user",
    "get_s3_client",
    "get_s3_service",
]
