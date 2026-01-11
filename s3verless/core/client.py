"""S3 client manager for handling S3 connections and operations."""

import asyncio
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
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


@dataclass
class PoolConfig:
    """Configuration for connection pool.

    Attributes:
        max_connections: Maximum number of connections in the pool
        connection_timeout: Timeout for acquiring a connection
        idle_timeout: How long idle connections are kept
    """

    max_connections: int = 10
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0


class S3ClientPool:
    """Connection pool for async S3 clients.

    This pool maintains a set of reusable S3 client connections to
    reduce the overhead of creating new connections for each request.
    """

    def __init__(
        self,
        settings: S3verlessSettings,
        config: PoolConfig | None = None,
    ):
        """Initialize the connection pool.

        Args:
            settings: S3verless settings
            config: Pool configuration
        """
        self.settings = settings
        self.config = config or PoolConfig()
        self._pool: asyncio.Queue | None = None
        self._session = None
        self._lock = asyncio.Lock()
        self._active_count = 0
        self._endpoint_url = adjust_endpoint_url(
            settings.aws_url, settings.aws_bucket_name
        )
        self._client_config = Config(
            s3={"addressing_style": "path"},
            retries={
                "max_attempts": settings.aws_retry_attempts,
                "mode": "standard",
            },
            max_pool_connections=self.config.max_connections,
        )

    async def _ensure_pool(self) -> None:
        """Ensure the pool is initialized."""
        if self._pool is None:
            async with self._lock:
                if self._pool is None:
                    self._pool = asyncio.Queue(maxsize=self.config.max_connections)
                    self._session = get_session()

    async def acquire(self) -> AioBaseClient:
        """Acquire a client from the pool.

        Returns:
            An S3 client

        Raises:
            S3ConnectionError: If unable to acquire a client
        """
        await self._ensure_pool()

        try:
            # Try to get an existing client from the pool
            try:
                client = self._pool.get_nowait()
                return client
            except asyncio.QueueEmpty:
                pass

            # Check if we can create a new client
            async with self._lock:
                if self._active_count < self.config.max_connections:
                    self._active_count += 1
                    try:
                        client = await self._create_client()
                        return client
                    except Exception:
                        self._active_count -= 1
                        raise

            # Wait for an available client
            try:
                client = await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self.config.connection_timeout,
                )
                return client
            except asyncio.TimeoutError:
                raise S3ConnectionError(
                    "Timed out waiting for available S3 connection",
                    endpoint=self._endpoint_url,
                )

        except S3ConnectionError:
            raise
        except Exception as e:
            raise S3ConnectionError(
                message=f"Failed to acquire S3 client: {e}",
                original_error=e,
                endpoint=self._endpoint_url,
            )

    async def release(self, client: AioBaseClient) -> None:
        """Release a client back to the pool.

        Args:
            client: The client to release
        """
        if self._pool is None:
            return

        try:
            self._pool.put_nowait(client)
        except asyncio.QueueFull:
            # Pool is full, close the client
            async with self._lock:
                self._active_count -= 1
            await client.close()

    async def _create_client(self) -> AioBaseClient:
        """Create a new S3 client.

        Returns:
            A new S3 client
        """
        return self._session.create_client(
            "s3",
            region_name=self.settings.aws_default_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
            endpoint_url=self._endpoint_url,
            config=self._client_config,
        )

    @asynccontextmanager
    async def client(self) -> AsyncGenerator[AioBaseClient, None]:
        """Context manager for acquiring and releasing clients.

        Yields:
            An S3 client
        """
        client = await self.acquire()
        try:
            # The client is a context manager itself
            async with client as c:
                yield c
        finally:
            await self.release(client)

    async def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is None:
            return

        async with self._lock:
            while not self._pool.empty():
                try:
                    client = self._pool.get_nowait()
                    await client.close()
                except asyncio.QueueEmpty:
                    break
            self._active_count = 0
            self._pool = None

    def stats(self) -> dict:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        return {
            "active_count": self._active_count,
            "max_connections": self.config.max_connections,
            "pool_size": self._pool.qsize() if self._pool else 0,
        }


class S3ClientManager:
    """Manages S3 client instances with proper lifecycle management.

    This class is a singleton that manages both synchronous and asynchronous
    S3 clients. It handles client creation, configuration, and cleanup.
    """

    _instance: "S3ClientManager | None" = None
    _sync_client: BaseClient | None = None
    _async_session = None
    _pool: S3ClientPool | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(
        cls,
        settings: S3verlessSettings | None = None,
        pool_config: PoolConfig | None = None,
    ) -> "S3ClientManager":
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize(
                        settings or S3verlessSettings(),
                        pool_config,
                    )
        return cls._instance

    def _initialize(
        self,
        settings: S3verlessSettings,
        pool_config: PoolConfig | None = None,
    ) -> None:
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
            # Initialize connection pool
            self._pool = S3ClientPool(settings, pool_config)

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
                raise S3ConnectionError(
                    message=f"Failed to create sync S3 client: {e}",
                    original_error=e,
                    endpoint=self._endpoint_url,
                )
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
            raise S3ConnectionError(
                message=f"Failed to create async S3 client: {e}",
                original_error=e,
                endpoint=self._endpoint_url,
            )

    @asynccontextmanager
    async def get_pooled_client(self) -> AsyncGenerator[AioBaseClient, None]:
        """Get a pooled async S3 client.

        This method uses the connection pool for better performance
        with high concurrency.

        Yields:
            An aiobotocore S3 client from the pool
        """
        async with self._pool.client() as client:
            yield client

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
            # Handle both numeric codes and named codes
            if error_code in ("404", "NoSuchBucket", "NotFound"):
                try:
                    client.create_bucket(Bucket=self.settings.aws_bucket_name)
                except ClientError as create_error:
                    raise S3ConnectionError(
                        message=f"Failed to create bucket: {create_error}",
                        original_error=create_error,
                        endpoint=self._endpoint_url,
                    )
            elif error_code == "403":
                raise S3OperationError("Permission denied checking bucket existence")
            else:
                raise S3OperationError(f"Error checking bucket: {e}")
        except Exception as e:
            raise S3ConnectionError(
                message=f"Unexpected error checking bucket: {e}",
                original_error=e,
                endpoint=self._endpoint_url,
            )

    async def close(self) -> None:
        """Close all connections and clean up resources."""
        if self._pool:
            await self._pool.close()
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    def pool_stats(self) -> dict:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        if self._pool:
            return self._pool.stats()
        return {}


# Global client manager instance (will be initialized by the app)
s3_manager: S3ClientManager | None = None
