"""Pytest fixtures for S3verless testing.

To use these fixtures, add to your conftest.py:

    pytest_plugins = ["s3verless.testing.fixtures"]

Or import specific fixtures:

    from s3verless.testing.fixtures import s3verless_settings, mock_s3
"""

import pytest
from typing import AsyncGenerator

from s3verless.core.registry import set_base_s3_path, reset_registry
from s3verless.core.settings import S3verlessSettings
from s3verless.testing.mocks import InMemoryS3
from s3verless.testing.utils import create_test_settings


@pytest.fixture
def s3verless_settings() -> S3verlessSettings:
    """Provide test settings for S3verless.

    Returns:
        S3verlessSettings instance configured for testing
    """
    return create_test_settings()


@pytest.fixture
def mock_s3() -> InMemoryS3:
    """Provide in-memory S3 mock.

    Returns:
        InMemoryS3 instance
    """
    s3 = InMemoryS3()
    yield s3
    s3.clear()


@pytest.fixture
def s3_test_bucket() -> str:
    """Provide test bucket name.

    Returns:
        Default test bucket name
    """
    return "test-bucket"


@pytest.fixture
def s3_base_path() -> str:
    """Provide test base path.

    Returns:
        Default test base path
    """
    return "test/"


@pytest.fixture(autouse=True)
def reset_s3verless_registry(s3_base_path: str):
    """Reset S3verless registry before each test.

    This fixture runs automatically for all tests and ensures
    a clean registry state.
    """
    reset_registry()
    set_base_s3_path(s3_base_path)
    yield
    reset_registry()


@pytest.fixture
async def s3_client(mock_s3: InMemoryS3) -> AsyncGenerator[InMemoryS3, None]:
    """Provide async S3 client for testing.

    This fixture provides an InMemoryS3 instance that can be used
    directly as an S3 client in tests.

    Yields:
        InMemoryS3 instance
    """
    # Ensure test bucket exists
    await mock_s3.create_bucket(Bucket="test-bucket")
    yield mock_s3


@pytest.fixture
def s3verless_test_app(
    s3verless_settings: S3verlessSettings,
    mock_s3: InMemoryS3,
):
    """Provide a test FastAPI app with mocked S3.

    This fixture creates a FastAPI test client with a mocked S3 backend.

    Yields:
        FastAPI TestClient with mocked S3
    """
    try:
        from fastapi.testclient import TestClient
        from s3verless import create_s3verless_app
    except ImportError:
        pytest.skip("fastapi or httpx not installed")
        return

    # Create app with test settings
    app = create_s3verless_app(
        settings=s3verless_settings,
        title="Test App",
        enable_admin=False,
        auto_discover=False,
    )

    # Override the S3 client dependency
    from s3verless.fastapi.dependencies import get_s3_client

    async def override_get_s3_client():
        yield mock_s3

    app.dependency_overrides[get_s3_client] = override_get_s3_client

    with TestClient(app) as client:
        yield client


# Additional utility fixtures

@pytest.fixture
def model_factory():
    """Provide a model factory creator.

    Returns:
        Function to create ModelFactory instances

    Example:
        def test_something(model_factory):
            ProductFactory = model_factory(Product)
            product = ProductFactory.build()
    """
    from s3verless.testing.factories import ModelFactory

    def _create_factory(model_class, **defaults):
        return ModelFactory(model_class, defaults=defaults)

    return _create_factory


@pytest.fixture
def data_generator():
    """Provide a data generator instance.

    Returns:
        DataGenerator instance

    Example:
        def test_something(data_generator):
            fake_email = data_generator._generate_email()
    """
    from s3verless.seeding.generator import DataGenerator
    return DataGenerator()
