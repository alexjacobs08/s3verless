"""Tests for testing utilities module."""

import pytest
import json
from typing import ClassVar
from botocore.exceptions import ClientError

from s3verless.core.base import BaseS3Model
from s3verless.testing.mocks import InMemoryS3, mock_s3_client
from s3verless.testing.factories import ModelFactory, factory_for


class UtilTestModel(BaseS3Model):
    """Test model for testing utilities."""

    _plural_name: ClassVar[str] = "util_test_models"

    name: str
    email: str
    price: float = 0.0
    is_active: bool = True


class TestInMemoryS3:
    """Tests for InMemoryS3 mock."""

    @pytest.mark.asyncio
    async def test_put_and_get_object(self):
        """Test putting and getting an object."""
        s3 = InMemoryS3()
        data = {"name": "test", "value": 123}

        await s3.put_object(
            Bucket="test-bucket",
            Key="test/key.json",
            Body=json.dumps(data).encode()
        )

        response = await s3.get_object(Bucket="test-bucket", Key="test/key.json")
        body = await response["Body"].read()
        result = json.loads(body.decode())

        assert result == data

    @pytest.mark.asyncio
    async def test_get_nonexistent_object(self):
        """Test getting an object that doesn't exist."""
        s3 = InMemoryS3()

        with pytest.raises(ClientError) as exc_info:
            await s3.get_object(Bucket="test-bucket", Key="nonexistent")

        assert exc_info.value.response["Error"]["Code"] == "NoSuchKey"

    @pytest.mark.asyncio
    async def test_delete_object(self):
        """Test deleting an object."""
        s3 = InMemoryS3()

        await s3.put_object(
            Bucket="test-bucket",
            Key="test/key.json",
            Body=b'{"test": true}'
        )

        await s3.delete_object(Bucket="test-bucket", Key="test/key.json")

        with pytest.raises(ClientError):
            await s3.get_object(Bucket="test-bucket", Key="test/key.json")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_object(self):
        """Test deleting a nonexistent object (should not raise)."""
        s3 = InMemoryS3()

        # Should not raise
        await s3.delete_object(Bucket="test-bucket", Key="nonexistent")

    @pytest.mark.asyncio
    async def test_list_objects_v2(self):
        """Test listing objects with prefix."""
        s3 = InMemoryS3()

        await s3.put_object(Bucket="bucket", Key="prefix/a.json", Body=b'{}')
        await s3.put_object(Bucket="bucket", Key="prefix/b.json", Body=b'{}')
        await s3.put_object(Bucket="bucket", Key="other/c.json", Body=b'{}')

        response = await s3.list_objects_v2(Bucket="bucket", Prefix="prefix/")

        assert "Contents" in response
        assert len(response["Contents"]) == 2
        keys = [obj["Key"] for obj in response["Contents"]]
        assert "prefix/a.json" in keys
        assert "prefix/b.json" in keys

    @pytest.mark.asyncio
    async def test_list_objects_empty(self):
        """Test listing objects when none exist."""
        s3 = InMemoryS3()

        response = await s3.list_objects_v2(Bucket="bucket", Prefix="empty/")

        assert response.get("KeyCount", 0) == 0

    @pytest.mark.asyncio
    async def test_head_object(self):
        """Test head object for existing object."""
        s3 = InMemoryS3()
        data = b'{"test": "data"}'

        await s3.put_object(Bucket="bucket", Key="test.json", Body=data)

        response = await s3.head_object(Bucket="bucket", Key="test.json")

        assert "ContentLength" in response
        assert response["ContentLength"] == len(data)

    @pytest.mark.asyncio
    async def test_head_object_not_found(self):
        """Test head object for nonexistent object."""
        s3 = InMemoryS3()

        with pytest.raises(ClientError) as exc_info:
            await s3.head_object(Bucket="bucket", Key="nonexistent")

        assert exc_info.value.response["Error"]["Code"] == "404"

    @pytest.mark.asyncio
    async def test_copy_object(self):
        """Test copying an object."""
        s3 = InMemoryS3()
        data = b'{"original": true}'

        await s3.put_object(Bucket="bucket", Key="source.json", Body=data)
        await s3.copy_object(
            Bucket="bucket",
            Key="dest.json",
            CopySource={"Bucket": "bucket", "Key": "source.json"}
        )

        response = await s3.get_object(Bucket="bucket", Key="dest.json")
        body = await response["Body"].read()

        assert body == data

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing all data."""
        s3 = InMemoryS3()

        await s3.put_object(Bucket="bucket", Key="a.json", Body=b'{}')
        await s3.put_object(Bucket="bucket", Key="b.json", Body=b'{}')

        s3.clear()

        response = await s3.list_objects_v2(Bucket="bucket")
        assert response.get("KeyCount", 0) == 0

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self):
        """Test generating presigned URL."""
        s3 = InMemoryS3()

        url = await s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": "bucket", "Key": "test.json"},
            ExpiresIn=3600
        )

        assert "bucket" in url
        assert "test.json" in url
        assert "presigned" in url

    @pytest.mark.asyncio
    async def test_generate_presigned_post(self):
        """Test generating presigned POST."""
        s3 = InMemoryS3()

        result = await s3.generate_presigned_post(
            Bucket="bucket",
            Key="uploads/test.pdf",
            ExpiresIn=3600
        )

        assert "url" in result
        assert "fields" in result
        assert result["fields"]["key"] == "uploads/test.pdf"


class TestMockS3ClientContextManager:
    """Tests for mock_s3_client context manager."""

    def test_context_manager(self):
        """Test using mock_s3_client as context manager."""
        with mock_s3_client() as s3:
            assert isinstance(s3, InMemoryS3)


class TestModelFactory:
    """Tests for ModelFactory class."""

    def test_build_creates_instance(self):
        """Test building a model instance."""
        factory = ModelFactory(UtilTestModel)

        instance = factory.build()

        assert isinstance(instance, UtilTestModel)
        assert instance.name is not None
        assert instance.email is not None

    def test_build_with_overrides(self):
        """Test building with field overrides."""
        factory = ModelFactory(UtilTestModel)

        instance = factory.build(name="Custom Name", price=99.99)

        assert instance.name == "Custom Name"
        assert instance.price == 99.99

    def test_build_multiple_unique(self):
        """Test building multiple unique instances."""
        factory = ModelFactory(UtilTestModel)

        instances = [factory.build() for _ in range(5)]

        # Each should have unique id
        ids = [inst.id for inst in instances]
        assert len(set(ids)) == 5

    def test_build_batch(self):
        """Test building a batch of instances."""
        factory = ModelFactory(UtilTestModel)

        instances = factory.build_batch(3)

        assert len(instances) == 3
        for inst in instances:
            assert isinstance(inst, UtilTestModel)

    @pytest.mark.asyncio
    async def test_create_saves_to_s3(self):
        """Test creating and saving an instance."""
        s3 = InMemoryS3()
        factory = ModelFactory(UtilTestModel)

        instance = await factory.create(s3, "test-bucket")

        # Verify it was saved - get the actual key from the model's prefix
        prefix = UtilTestModel.get_s3_prefix()
        key = f"{prefix}{instance.id}.json"
        response = await s3.get_object(Bucket="test-bucket", Key=key)
        body = await response["Body"].read()
        data = json.loads(body.decode())

        assert data["name"] == instance.name

    @pytest.mark.asyncio
    async def test_create_with_overrides(self):
        """Test creating with overrides."""
        s3 = InMemoryS3()
        factory = ModelFactory(UtilTestModel)

        instance = await factory.create(s3, "test-bucket", name="Specific Name")

        assert instance.name == "Specific Name"

    @pytest.mark.asyncio
    async def test_create_batch(self):
        """Test creating a batch of instances."""
        s3 = InMemoryS3()
        factory = ModelFactory(UtilTestModel)

        instances = await factory.create_batch(s3, "test-bucket", count=3)

        assert len(instances) == 3
        for inst in instances:
            assert isinstance(inst, UtilTestModel)

    def test_with_defaults(self):
        """Test creating factory with defaults."""
        factory = ModelFactory(UtilTestModel)
        factory_with_defaults = factory.with_defaults(is_active=True, price=10.0)

        instance = factory_with_defaults.build()

        assert instance.is_active is True
        assert instance.price == 10.0


class TestFactoryFor:
    """Tests for factory_for convenience function."""

    def test_factory_for_creates_factory(self):
        """Test factory_for creates a ModelFactory."""
        factory = factory_for(UtilTestModel)

        assert isinstance(factory, ModelFactory)

    def test_factory_for_with_defaults(self):
        """Test factory_for with defaults."""
        factory = factory_for(UtilTestModel, is_active=False)

        instance = factory.build()

        assert instance.is_active is False
