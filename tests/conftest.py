"""Pytest configuration and fixtures for s3verless tests."""

import json
from datetime import datetime
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock

import boto3
import pytest
from botocore.response import StreamingBody
from moto import mock_aws

from s3verless.core.client import S3ClientManager
from s3verless.core.registry import _model_metadata, _model_registry, set_base_s3_path
from s3verless.core.settings import S3verlessSettings


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the model registry before each test."""
    _model_registry.clear()
    _model_metadata.clear()
    set_base_s3_path("test/")
    yield
    _model_registry.clear()
    _model_metadata.clear()


@pytest.fixture
def test_settings():
    """Create test settings."""
    return S3verlessSettings(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_default_region="us-east-1",
        aws_bucket_name="test-bucket",
        secret_key="test-secret-key",
        s3_base_path="test/",
    )


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client using moto."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")
        yield client


@pytest.fixture
async def async_mock_s3_client():
    """Create an async mock S3 client with in-memory storage."""
    from botocore.exceptions import ClientError

    # In-memory storage for S3 objects
    storage = {}

    client = AsyncMock()

    # Mock list_objects_v2
    async def mock_list_objects_v2(**kwargs):
        bucket = kwargs.get("Bucket")
        prefix = kwargs.get("Prefix", "")
        max_keys = kwargs.get("MaxKeys", 1000)

        # Find all keys matching prefix
        matching_keys = [
            {"Key": key, "Size": len(storage[key])}
            for key in storage
            if key.startswith(prefix)
        ][:max_keys]

        return {"Contents": matching_keys, "IsTruncated": False}

    client.list_objects_v2 = AsyncMock(side_effect=mock_list_objects_v2)

    # Mock get_object
    async def mock_get_object(Bucket: str, Key: str, **kwargs):
        """Mock get_object response."""
        if Key not in storage:
            error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
            raise ClientError(error_response, "GetObject")

        data = storage[Key]
        body_mock = AsyncMock()
        body_mock.read = AsyncMock(return_value=data)
        return {"Body": body_mock, "ContentType": "application/json"}

    client.get_object = AsyncMock(side_effect=mock_get_object)

    # Mock put_object
    async def mock_put_object(Bucket: str, Key: str, Body: bytes, **kwargs):
        """Mock put_object."""
        storage[Key] = Body if isinstance(Body, bytes) else Body.encode("utf-8")
        return {"ETag": "test-etag"}

    client.put_object = AsyncMock(side_effect=mock_put_object)

    # Mock delete_object
    async def mock_delete_object(Bucket: str, Key: str, **kwargs):
        """Mock delete_object."""
        storage.pop(Key, None)
        return {}

    client.delete_object = AsyncMock(side_effect=mock_delete_object)

    # Mock head_object
    async def mock_head_object(Bucket: str, Key: str, **kwargs):
        """Mock head_object."""
        if Key not in storage:
            error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
            raise ClientError(error_response, "HeadObject")
        return {"ContentLength": len(storage[Key])}

    client.head_object = AsyncMock(side_effect=mock_head_object)

    # Add storage reference for tests that need to populate data
    client._storage = storage

    return client


@pytest.fixture
def s3_client_manager(test_settings):
    """Create an S3 client manager for testing."""
    return S3ClientManager(test_settings)


@pytest.fixture
def sample_model_data():
    """Sample model data for testing."""
    return {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "name": "Test Item",
        "value": 42,
    }


@pytest.fixture
def mock_s3_response():
    """Create a mock S3 response object."""

    def _create_response(data: dict[str, Any]):
        """Create a streaming body response."""
        json_data = json.dumps(data).encode("utf-8")
        return {
            "Body": StreamingBody(BytesIO(json_data), len(json_data)),
            "ContentType": "application/json",
            "ContentLength": len(json_data),
        }

    return _create_response
