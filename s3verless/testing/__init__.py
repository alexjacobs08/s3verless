"""Testing utilities for S3verless applications.

This module provides utilities for testing S3verless applications,
including mock S3 clients, test fixtures, and model factories.

Usage in conftest.py:
    from s3verless.testing import (
        mock_s3_client,
        create_test_settings,
        InMemoryS3,
        ModelFactory,
    )

    @pytest.fixture
    def s3_client():
        with mock_s3_client() as client:
            yield client

Or use provided fixtures directly:
    pytest_plugins = ["s3verless.testing.fixtures"]
"""

from s3verless.testing.mocks import InMemoryS3, mock_s3_client
from s3verless.testing.factories import ModelFactory
from s3verless.testing.utils import create_test_settings, S3TestCase

__all__ = [
    "InMemoryS3",
    "mock_s3_client",
    "ModelFactory",
    "create_test_settings",
    "S3TestCase",
]
