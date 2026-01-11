"""Testing utilities for S3verless applications."""

import asyncio
from typing import Type
from unittest import IsolatedAsyncioTestCase

from s3verless.core.base import BaseS3Model
from s3verless.core.registry import set_base_s3_path, reset_registry
from s3verless.core.settings import S3verlessSettings
from s3verless.testing.mocks import InMemoryS3


def create_test_settings(
    bucket_name: str = "test-bucket",
    base_path: str = "test/",
    secret_key: str = "test-secret-key-for-testing-only",
    **overrides
) -> S3verlessSettings:
    """Create S3verless settings for testing.

    Args:
        bucket_name: The S3 bucket name for tests
        base_path: The S3 base path for tests
        secret_key: JWT secret key for tests
        **overrides: Additional settings to override

    Returns:
        S3verlessSettings instance configured for testing
    """
    return S3verlessSettings(
        aws_bucket_name=bucket_name,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        aws_default_region="us-east-1",
        aws_url="http://localhost:4566",
        secret_key=secret_key,
        s3_base_path=base_path,
        debug=True,
        create_default_admin=False,
        **overrides,
    )


class S3TestCase(IsolatedAsyncioTestCase):
    """Base test case class for S3verless tests.

    This class provides a pre-configured test environment with:
    - In-memory S3 mock
    - Test settings
    - Automatic registry reset between tests

    Example:
        >>> class TestMyModel(S3TestCase):
        ...     async def test_create_item(self):
        ...         from myapp.models import Item
        ...         from s3verless.core.service import S3DataService
        ...
        ...         service = S3DataService(Item, self.bucket_name)
        ...         item = Item(name="Test")
        ...         created = await service.create(self.s3_client, item)
        ...         self.assertEqual(created.name, "Test")
    """

    bucket_name: str = "test-bucket"
    base_path: str = "test/"

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        # Reset registry for clean state
        reset_registry()
        # Set base path
        set_base_s3_path(self.base_path)
        # Create mock S3 client
        self.s3_client = InMemoryS3()
        # Create test settings
        self.settings = create_test_settings(
            bucket_name=self.bucket_name,
            base_path=self.base_path,
        )

    def tearDown(self) -> None:
        """Clean up after test."""
        self.s3_client.clear()
        reset_registry()
        super().tearDown()

    async def create_model_instance(
        self,
        model_class: Type[BaseS3Model],
        **data
    ) -> BaseS3Model:
        """Create and save a model instance.

        Args:
            model_class: The model class to create
            **data: Data for the model

        Returns:
            The created model instance
        """
        from s3verless.core.service import S3DataService
        from s3verless.testing.factories import ModelFactory

        factory = ModelFactory(model_class)
        instance = factory.build(**data)
        service = S3DataService(model_class, self.bucket_name)
        return await service.create(self.s3_client, instance)

    async def get_model_instance(
        self,
        model_class: Type[BaseS3Model],
        instance_id
    ) -> BaseS3Model | None:
        """Retrieve a model instance by ID.

        Args:
            model_class: The model class
            instance_id: The instance ID

        Returns:
            The model instance or None if not found
        """
        from s3verless.core.service import S3DataService
        service = S3DataService(model_class, self.bucket_name)
        return await service.get(self.s3_client, instance_id)

    def assertModelEqual(
        self,
        model1: BaseS3Model,
        model2: BaseS3Model,
        exclude_fields: list[str] | None = None
    ) -> None:
        """Assert two model instances are equal.

        Args:
            model1: First model instance
            model2: Second model instance
            exclude_fields: Fields to exclude from comparison
        """
        exclude = set(exclude_fields or [])
        exclude.add("updated_at")  # Always exclude updated_at

        data1 = model1.model_dump()
        data2 = model2.model_dump()

        for field in exclude:
            data1.pop(field, None)
            data2.pop(field, None)

        self.assertEqual(data1, data2)
