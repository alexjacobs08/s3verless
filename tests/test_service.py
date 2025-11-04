"""Tests for S3DataService."""

import json
import uuid

import pytest

from s3verless.core.base import BaseS3Model
from s3verless.core.service import S3DataService


class SampleModel(BaseS3Model):
    """Sample model for testing."""

    name: str
    value: int


@pytest.fixture
def service():
    """Create a service instance for testing."""
    return S3DataService(SampleModel, "test-bucket")


@pytest.fixture
async def s3_setup(async_mock_s3_client):
    """Set up S3 mock and bucket with async client."""
    return async_mock_s3_client


class TestS3DataService:
    """Tests for S3DataService class."""

    @pytest.mark.asyncio
    async def test_create_item(self, service, s3_setup):
        """Test creating an item in S3."""
        item = SampleModel(name="Test", value=42)

        result = await service.create(s3_setup, item)

        assert result is not None
        assert result.id == item.id
        assert result.name == "Test"
        assert result.value == 42

        # Verify it was saved to S3
        key = item.s3_key
        response = await s3_setup.get_object(Bucket="test-bucket", Key=key)
        content = await response["Body"].read()
        data = json.loads(content)

        assert data["name"] == "Test"
        assert data["value"] == 42

    @pytest.mark.asyncio
    async def test_get_item(self, service, s3_setup):
        """Test getting an item from S3."""
        # Create item first
        item = SampleModel(name="Test", value=42)
        key = item.s3_key

        await s3_setup.put_object(
            Bucket="test-bucket",
            Key=key,
            Body=json.dumps(item.model_dump(), default=str),
            ContentType="application/json",
        )

        # Get the item
        result = await service.get(s3_setup, str(item.id))

        assert result is not None
        assert result.id == item.id
        assert result.name == "Test"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_get_nonexistent_item(self, service, s3_setup):
        """Test getting an item that doesn't exist."""
        result = await service.get(s3_setup, str(uuid.uuid4()))
        assert result is None

    @pytest.mark.asyncio
    async def test_update_item(self, service, s3_setup):
        """Test updating an item in S3."""
        # Create item
        item = SampleModel(name="Original", value=10)
        await service.create(s3_setup, item)

        # Update it
        item.name = "Updated"
        item.value = 20
        result = await service.update(s3_setup, str(item.id), item)

        assert result is not None
        assert result.name == "Updated"
        assert result.value == 20

        # Verify in S3
        retrieved = await service.get(s3_setup, str(item.id))
        assert retrieved.name == "Updated"
        assert retrieved.value == 20

    @pytest.mark.asyncio
    async def test_delete_item(self, service, s3_setup):
        """Test deleting an item from S3."""
        # Create item
        item = SampleModel(name="ToDelete", value=99)
        await service.create(s3_setup, item)

        # Delete it
        await service.delete(s3_setup, str(item.id))

        # Verify it's gone
        result = await service.get(s3_setup, str(item.id))
        assert result is None

    @pytest.mark.asyncio
    async def test_list_items(self, service, s3_setup):
        """Test listing items with pagination."""
        # Create multiple items
        items = [SampleModel(name=f"Item {i}", value=i) for i in range(5)]

        for item in items:
            await service.create(s3_setup, item)

        # List items
        result = await service.paginate(s3_setup, page=1, page_size=3)

        assert len(result["items"]) == 3
        assert result["total_count"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 3
        assert result["has_next"] is True
        assert result["has_prev"] is False

    @pytest.mark.asyncio
    async def test_list_items_pagination(self, service, s3_setup):
        """Test pagination in list operations."""
        # Create items
        items = [SampleModel(name=f"Item {i}", value=i) for i in range(10)]
        for item in items:
            await service.create(s3_setup, item)

        # Get page 1
        page1 = await service.paginate(s3_setup, page=1, page_size=4)

        # Get page 2
        page2 = await service.paginate(s3_setup, page=2, page_size=4)

        assert len(page1["items"]) == 4
        assert len(page2["items"]) == 4
        assert page1["has_next"] is True
        assert page1["has_prev"] is False
        assert page2["has_next"] is True
        assert page2["has_prev"] is True

    @pytest.mark.asyncio
    async def test_exists(self, service, s3_setup):
        """Test checking if an item exists."""
        # Create item
        item = SampleModel(name="Test", value=42)
        await service.create(s3_setup, item)

        # Check exists
        assert await service.exists(s3_setup, str(item.id)) is True
        assert await service.exists(s3_setup, str(uuid.uuid4())) is False

    @pytest.mark.asyncio
    async def test_create_with_custom_id(self, service, s3_setup):
        """Test creating an item with a custom UUID."""
        custom_id = uuid.uuid4()
        item = SampleModel(id=custom_id, name="Custom ID", value=123)

        result = await service.create(s3_setup, item)

        assert result.id == custom_id

        # Verify retrieval
        retrieved = await service.get(s3_setup, str(custom_id))
        assert retrieved is not None
        assert retrieved.id == custom_id
