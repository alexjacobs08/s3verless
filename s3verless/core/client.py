"""S3 client manager for handling S3 connections and operations."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Protocol, runtime_checkable

from aiobotocore.client import AioBaseClient
from aiobotocore.session import get_session
from boto3.session import Session
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from s3verless.core.exceptions import S3ConnectionError, S3OperationError
from s3verless.core.settings import S3verlessSettings


@runtime_checkable
class S3ClientProtocol(Protocol):
    """Protocol for S3 client operations."""

    async def get_object(self, Bucket: str, Key: str, **kwargs) -> dict[str, Any]:
        """Get an object from S3."""
        ...

    async def put_object(
        self, Bucket: str, Key: str, Body: bytes | str, **kwargs
    ) -> dict[str, Any]:
        """Put an object to S3."""
        ...

    async def delete_object(self, Bucket: str, Key: str, **kwargs) -> dict[str, Any]:
        """Delete an object from S3."""
        ...

    async def list_objects_v2(self, Bucket: str, **kwargs) -> dict[str, Any]:
        """List objects in S3."""
        ...

    async def head_object(self, Bucket: str, Key: str, **kwargs) -> dict[str, Any]:
        """Get object metadata."""
        ...


def adjust_endpoint_url(
    endpoint_url: str | None, bucket_name: str | None
) -> str | None:
    """Adjust endpoint URL for path-style addressing if needed.

    Args:
        endpoint_url: The S3 endpoint URL
        bucket_name: The S3 bucket name

    Returns:
        Adjusted endpoint URL or None
    """
    if not endpoint_url:
        return None
    if bucket_name and f"{bucket_name}." in endpoint_url:
        return endpoint_url.replace(f"{bucket_name}.", "")
    return endpoint_url


class S3ClientManager:
    """Manages S3 client instances with proper lifecycle management.

    This class is a singleton that manages both synchronous and asynchronous
    S3 clients. It handles client creation, configuration, and cleanup.
    """

    _instance: "S3ClientManager | None" = None
    _sync_client: BaseClient | None = None
    _async_session = None

    def __new__(cls, settings: S3verlessSettings | None = None) -> "S3ClientManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(settings or S3verlessSettings())
        return cls._instance

    def _initialize(self, settings: S3verlessSettings) -> None:
        """Initialize the client manager with settings."""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.settings = settings
            self._endpoint_url = adjust_endpoint_url(
                settings.aws_url, settings.aws_bucket_name
            )
            self._client_config = Config(
                s3={"addressing_style": "path"},
                retries={
                    "max_attempts": settings.aws_retry_attempts,
                    "mode": "standard",
                },
            )

    def get_sync_client(self) -> BaseClient:
        """Get or create a synchronized S3 client.

        Returns:
            A boto3 S3 client

        Raises:
            S3ConnectionError: If client creation fails
        """
        if self._sync_client is None:
            try:
                session = Session()
                self._sync_client = session.client(
                    "s3",
                    region_name=self.settings.aws_default_region,
                    aws_access_key_id=self.settings.aws_access_key_id,
                    aws_secret_access_key=self.settings.aws_secret_access_key,
                    endpoint_url=self._endpoint_url,
                    config=self._client_config,
                )
            except Exception as e:
                raise S3ConnectionError(f"Failed to create sync S3 client: {e}")
        return self._sync_client

    @asynccontextmanager
    async def get_async_client(self) -> AsyncGenerator[AioBaseClient, None]:
        """Get an async S3 client within a context manager.

        Yields:
            An aiobotocore S3 client

        Raises:
            S3ConnectionError: If client creation fails
            S3OperationError: If client operations fail
        """
        if self._async_session is None:
            self._async_session = get_session()

        try:
            async with self._async_session.create_client(
                "s3",
                region_name=self.settings.aws_default_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                endpoint_url=self._endpoint_url,
                config=self._client_config,
            ) as client:
                yield client
        except ClientError as e:
            raise S3OperationError(f"S3 client operation failed: {e}")
        except Exception as e:
            raise S3ConnectionError(f"Failed to create async S3 client: {e}")

    async def get_async_client_dependency(self) -> AsyncGenerator[AioBaseClient, None]:
        """FastAPI dependency to get an async S3 client.

        This is a convenience method for use with FastAPI's dependency injection.

        Yields:
            An aiobotocore S3 client
        """
        async with self.get_async_client() as client:
            yield client

    async def ensure_bucket_exists(self) -> None:
        """Ensure the configured S3 bucket exists, creating it if necessary.

        Raises:
            S3ConnectionError: If bucket creation fails
            S3OperationError: If bucket check fails
        """
        client = self.get_sync_client()
        try:
            client.head_bucket(Bucket=self.settings.aws_bucket_name)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                try:
                    client.create_bucket(Bucket=self.settings.aws_bucket_name)
                except ClientError as create_error:
                    raise S3ConnectionError(f"Failed to create bucket: {create_error}")
            elif error_code == "403":
                raise S3OperationError("Permission denied checking bucket existence")
            else:
                raise S3OperationError(f"Error checking bucket: {e}")
        except Exception as e:
            raise S3ConnectionError(f"Unexpected error checking bucket: {e}")


# Global client manager instance (will be initialized by the app)
s3_manager: S3ClientManager | None = None
