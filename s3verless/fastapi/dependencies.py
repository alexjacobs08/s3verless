"""FastAPI dependency injection utilities for S3verless."""

from collections.abc import AsyncGenerator
from typing import Type, TypeVar

from aiobotocore.client import AioBaseClient
from fastapi import Depends, Request

from s3verless.auth.service import S3AuthService
from s3verless.core.base import BaseS3Model
from s3verless.core.client import S3ClientManager
from s3verless.core.service import S3DataService
from s3verless.core.settings import S3verlessSettings

# Type variable for S3 models
T = TypeVar("T", bound=BaseS3Model)


def get_settings(request: Request) -> S3verlessSettings:
    """Get S3verless settings.

    Retrieves settings from app.state if available, otherwise creates from env vars.

    Args:
        request: FastAPI request object

    Returns:
        The settings instance
    """
    # Try to get settings from app state (injected by S3verless)
    if hasattr(request.app.state, "settings"):
        return request.app.state.settings
    # Fall back to creating from environment variables
    return S3verlessSettings()


def get_client_manager(
    settings: S3verlessSettings = Depends(get_settings),
) -> S3ClientManager:
    """Get S3 client manager.

    Args:
        settings: The settings instance

    Returns:
        The client manager instance
    """
    return S3ClientManager(settings)


async def get_s3_client(
    client_manager: S3ClientManager = Depends(get_client_manager),
) -> AsyncGenerator[AioBaseClient, None]:
    """Get an async S3 client.

    Args:
        client_manager: The client manager instance

    Yields:
        An async S3 client
    """
    async with client_manager.get_async_client() as client:
        yield client


def get_auth_service(
    settings: S3verlessSettings = Depends(get_settings),
) -> S3AuthService:
    """Get authentication service.

    Args:
        settings: The settings instance

    Returns:
        The auth service instance
    """
    return S3AuthService(
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        bucket_name=settings.aws_bucket_name,
    )


def get_s3_service(model_type: Type[T]) -> S3DataService[T]:
    """Get S3 data service for a specific model.

    Args:
        model_type: The model class to create a service for

    Returns:
        A function that creates the service instance
    """

    def _get_service(
        settings: S3verlessSettings = Depends(get_settings),
    ) -> S3DataService[T]:
        return S3DataService[model_type](model_type, settings.aws_bucket_name)

    return _get_service
