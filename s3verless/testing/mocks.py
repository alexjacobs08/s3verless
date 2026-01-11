"""Mock S3 client for testing S3verless applications."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock

from botocore.exceptions import ClientError


class InMemoryS3:
    """In-memory S3 mock for testing without external dependencies.

    This class provides a fully async-compatible mock S3 client that stores
    all data in memory. It implements the key S3 operations used by S3verless.

    Example:
        >>> s3 = InMemoryS3()
        >>> await s3.put_object(Bucket="test", Key="data.json", Body=b'{"id": 1}')
        >>> response = await s3.get_object(Bucket="test", Key="data.json")
        >>> data = await response["Body"].read()
    """

    def __init__(self):
        """Initialize the in-memory S3 mock."""
        # Storage: {bucket_name: {key: bytes}}
        self._storage: Dict[str, Dict[str, bytes]] = {}
        # Metadata: {bucket_name: {key: dict}}
        self._metadata: Dict[str, Dict[str, dict]] = {}

    def _ensure_bucket(self, bucket: str) -> None:
        """Ensure a bucket exists in storage."""
        if bucket not in self._storage:
            self._storage[bucket] = {}
            self._metadata[bucket] = {}

    async def create_bucket(self, Bucket: str, **kwargs) -> dict:
        """Create a new bucket.

        Args:
            Bucket: The bucket name

        Returns:
            Empty dict (matches S3 API)
        """
        self._ensure_bucket(Bucket)
        return {}

    async def head_bucket(self, Bucket: str, **kwargs) -> dict:
        """Check if a bucket exists.

        Args:
            Bucket: The bucket name

        Returns:
            Empty dict if bucket exists

        Raises:
            ClientError: If bucket doesn't exist
        """
        if Bucket not in self._storage:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Bucket not found"}},
                "HeadBucket"
            )
        return {}

    async def put_object(
        self,
        Bucket: str,
        Key: str,
        Body: bytes | str,
        ContentType: str = "application/octet-stream",
        **kwargs
    ) -> dict:
        """Store an object in the mock S3.

        Args:
            Bucket: The bucket name
            Key: The object key
            Body: The object data (bytes or string)
            ContentType: The content type

        Returns:
            Dict with ETag
        """
        self._ensure_bucket(Bucket)

        if isinstance(Body, str):
            Body = Body.encode("utf-8")

        self._storage[Bucket][Key] = Body
        self._metadata[Bucket][Key] = {
            "ContentType": ContentType,
            "ContentLength": len(Body),
            "LastModified": datetime.now(timezone.utc),
            "ETag": f'"{hash(Body)}"',
            **{k: v for k, v in kwargs.items() if k.startswith("x-amz-meta-")},
        }

        return {"ETag": self._metadata[Bucket][Key]["ETag"]}

    async def get_object(self, Bucket: str, Key: str, **kwargs) -> dict:
        """Retrieve an object from the mock S3.

        Args:
            Bucket: The bucket name
            Key: The object key

        Returns:
            Dict with Body (AsyncMock with read method)

        Raises:
            ClientError: If object doesn't exist
        """
        if Bucket not in self._storage or Key not in self._storage[Bucket]:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
                "GetObject"
            )

        body = AsyncMock()
        body.read = AsyncMock(return_value=self._storage[Bucket][Key])

        metadata = self._metadata[Bucket].get(Key, {})

        return {
            "Body": body,
            "ContentType": metadata.get("ContentType", "application/octet-stream"),
            "ContentLength": metadata.get("ContentLength", len(self._storage[Bucket][Key])),
            "LastModified": metadata.get("LastModified", datetime.now(timezone.utc)),
            "ETag": metadata.get("ETag", '"mock-etag"'),
        }

    async def delete_object(self, Bucket: str, Key: str, **kwargs) -> dict:
        """Delete an object from the mock S3.

        Args:
            Bucket: The bucket name
            Key: The object key

        Returns:
            Empty dict
        """
        if Bucket in self._storage and Key in self._storage[Bucket]:
            del self._storage[Bucket][Key]
            if Key in self._metadata.get(Bucket, {}):
                del self._metadata[Bucket][Key]
        return {}

    async def head_object(self, Bucket: str, Key: str, **kwargs) -> dict:
        """Get object metadata without retrieving the object.

        Args:
            Bucket: The bucket name
            Key: The object key

        Returns:
            Dict with object metadata

        Raises:
            ClientError: If object doesn't exist
        """
        if Bucket not in self._storage or Key not in self._storage[Bucket]:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadObject"
            )

        metadata = self._metadata[Bucket].get(Key, {})
        return {
            "ContentLength": metadata.get("ContentLength", len(self._storage[Bucket][Key])),
            "ContentType": metadata.get("ContentType", "application/octet-stream"),
            "LastModified": metadata.get("LastModified", datetime.now(timezone.utc)),
            "ETag": metadata.get("ETag", '"mock-etag"'),
        }

    async def list_objects_v2(
        self,
        Bucket: str,
        Prefix: str = "",
        MaxKeys: int = 1000,
        ContinuationToken: str | None = None,
        **kwargs
    ) -> dict:
        """List objects in a bucket.

        Args:
            Bucket: The bucket name
            Prefix: Filter by key prefix
            MaxKeys: Maximum number of keys to return
            ContinuationToken: Pagination token

        Returns:
            Dict with Contents and pagination info
        """
        if Bucket not in self._storage:
            return {"KeyCount": 0}

        all_keys = sorted([
            key for key in self._storage[Bucket].keys()
            if key.startswith(Prefix)
        ])

        # Handle pagination
        start_idx = 0
        if ContinuationToken:
            try:
                start_idx = int(ContinuationToken)
            except ValueError:
                start_idx = 0

        end_idx = start_idx + MaxKeys
        page_keys = all_keys[start_idx:end_idx]

        if not page_keys:
            return {"KeyCount": 0}

        contents = []
        for key in page_keys:
            metadata = self._metadata[Bucket].get(key, {})
            contents.append({
                "Key": key,
                "Size": metadata.get("ContentLength", len(self._storage[Bucket][key])),
                "LastModified": metadata.get("LastModified", datetime.now(timezone.utc)),
                "ETag": metadata.get("ETag", '"mock-etag"'),
            })

        result = {
            "Contents": contents,
            "KeyCount": len(contents),
            "MaxKeys": MaxKeys,
            "Prefix": Prefix,
            "IsTruncated": end_idx < len(all_keys),
        }

        if result["IsTruncated"]:
            result["NextContinuationToken"] = str(end_idx)

        return result

    async def list_buckets(self, **kwargs) -> dict:
        """List all buckets.

        Returns:
            Dict with Buckets list
        """
        return {
            "Buckets": [
                {"Name": name, "CreationDate": datetime.now(timezone.utc)}
                for name in self._storage.keys()
            ]
        }

    async def copy_object(
        self,
        Bucket: str,
        Key: str,
        CopySource: dict,
        **kwargs
    ) -> dict:
        """Copy an object within S3.

        Args:
            Bucket: Destination bucket
            Key: Destination key
            CopySource: Dict with Bucket and Key of source

        Returns:
            Dict with copy result
        """
        source_bucket = CopySource.get("Bucket", CopySource.get("bucket"))
        source_key = CopySource.get("Key", CopySource.get("key"))

        if source_bucket not in self._storage or source_key not in self._storage[source_bucket]:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Source object not found"}},
                "CopyObject"
            )

        self._ensure_bucket(Bucket)
        self._storage[Bucket][Key] = self._storage[source_bucket][source_key]
        self._metadata[Bucket][Key] = self._metadata[source_bucket].get(source_key, {}).copy()

        return {"CopyObjectResult": {"ETag": self._metadata[Bucket][Key].get("ETag", '"mock-etag"')}}

    async def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict,
        ExpiresIn: int = 3600,
        **kwargs
    ) -> str:
        """Generate a presigned URL (mock implementation).

        Args:
            ClientMethod: The S3 operation (e.g., 'get_object', 'put_object')
            Params: Parameters for the operation
            ExpiresIn: URL expiration time in seconds

        Returns:
            A mock presigned URL
        """
        bucket = Params.get("Bucket", "bucket")
        key = Params.get("Key", "key")
        return f"https://{bucket}.s3.amazonaws.com/{key}?mock-presigned=true&expires={ExpiresIn}"

    async def generate_presigned_post(
        self,
        Bucket: str,
        Key: str,
        Conditions: list | None = None,
        ExpiresIn: int = 3600,
        Fields: dict | None = None,
        **kwargs
    ) -> dict:
        """Generate presigned POST data (mock implementation).

        Args:
            Bucket: The bucket name
            Key: The object key
            Conditions: Upload conditions
            ExpiresIn: URL expiration time
            Fields: Additional form fields

        Returns:
            Dict with url and fields for POST upload
        """
        return {
            "url": f"https://{Bucket}.s3.amazonaws.com",
            "fields": {
                "key": Key,
                **(Fields or {}),
                "policy": "mock-policy",
                "x-amz-signature": "mock-signature",
            }
        }

    def clear(self) -> None:
        """Clear all stored data."""
        self._storage.clear()
        self._metadata.clear()

    def get_bucket_data(self, bucket: str) -> dict:
        """Get all data in a bucket (for testing assertions).

        Args:
            bucket: The bucket name

        Returns:
            Dict of {key: data} for the bucket
        """
        return {
            key: json.loads(data.decode("utf-8"))
            for key, data in self._storage.get(bucket, {}).items()
            if data
        }


@contextmanager
def mock_s3_client():
    """Context manager providing an in-memory S3 mock.

    Example:
        >>> with mock_s3_client() as s3:
        ...     await s3.put_object(Bucket="test", Key="data.json", Body=b'{}')
        ...     response = await s3.get_object(Bucket="test", Key="data.json")

    Yields:
        InMemoryS3 instance
    """
    mock = InMemoryS3()
    try:
        yield mock
    finally:
        mock.clear()
