"""Tests for BaseS3Model."""

import uuid
from datetime import datetime

import pytest
from pydantic import Field

from s3verless.core.base import BaseS3Model, aware_now
from s3verless.core.registry import set_base_s3_path


class TestAwareNow:
    """Tests for aware_now utility function."""

    def test_returns_aware_datetime(self):
        """Test that aware_now returns timezone-aware datetime."""
        now = aware_now()
        assert now.tzinfo is not None
        assert isinstance(now, datetime)


class TestBaseS3Model:
    """Tests for BaseS3Model class."""

    def test_auto_id_generation(self):
        """Test that models are created with auto-generated UUIDs."""

        class Product(BaseS3Model):
            name: str
            price: float

        product = Product(name="Test Product", price=9.99)
        assert isinstance(product.id, uuid.UUID)
        assert product.id is not None

    def test_auto_timestamps(self):
        """Test that created_at and updated_at are auto-generated."""

        class Product(BaseS3Model):
            name: str

        product = Product(name="Test")
        assert isinstance(product.created_at, datetime)
        assert isinstance(product.updated_at, datetime)
        assert product.created_at.tzinfo is not None
        assert product.updated_at.tzinfo is not None

    def test_s3_key_generation(self):
        """Test S3 key generation for model instances."""
        set_base_s3_path("test-base/")

        class User(BaseS3Model):
            username: str

        user = User(username="testuser")
        key = user.s3_key

        assert key.startswith("test-base/")
        assert str(user.id) in key
        assert key.endswith(".json")

    def test_get_s3_key_class_method(self):
        """Test get_s3_key class method."""
        set_base_s3_path("data/")

        class Item(BaseS3Model):
            name: str

        test_id = uuid.uuid4()
        key = Item.get_s3_key(test_id)

        assert key.startswith("data/")
        assert str(test_id) in key
        assert key.endswith(".json")

    def test_get_s3_prefix(self):
        """Test get_s3_prefix class method."""
        set_base_s3_path("myapp/")

        class Product(BaseS3Model):
            name: str

        prefix = Product.get_s3_prefix()
        assert prefix.startswith("myapp/")
        assert "product" in prefix.lower()
        assert prefix.endswith("/")

    def test_touch_method(self):
        """Test that touch() updates the updated_at timestamp."""

        class Item(BaseS3Model):
            name: str

        item = Item(name="Test")
        original_updated_at = item.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        item.touch()
        assert item.updated_at > original_updated_at

    def test_model_with_custom_fields(self):
        """Test model with custom field definitions."""

        class Product(BaseS3Model):
            _plural_name = "products"
            _indexes = ["category", "price"]
            _unique_fields = ["sku"]

            name: str = Field(..., min_length=1)
            sku: str
            price: float = Field(..., gt=0)
            category: str

        product = Product(name="Widget", sku="WDG-001", price=19.99, category="gadgets")

        assert product.name == "Widget"
        assert product.sku == "WDG-001"
        assert product._plural_name == "products"
        assert "category" in product._indexes
        assert "sku" in product._unique_fields

    def test_model_serialization(self):
        """Test that models can be serialized to dict."""

        class User(BaseS3Model):
            username: str
            email: str

        user = User(username="john", email="john@example.com")
        data = user.model_dump()

        assert isinstance(data, dict)
        assert data["username"] == "john"
        assert data["email"] == "john@example.com"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_model_json_serialization(self):
        """Test that models can be serialized to JSON."""

        class Product(BaseS3Model):
            name: str
            price: float

        product = Product(name="Test", price=9.99)
        json_str = product.model_dump_json()

        assert isinstance(json_str, str)
        assert "Test" in json_str
        assert "9.99" in json_str

    def test_model_validation(self):
        """Test that Pydantic validation works."""

        class Product(BaseS3Model):
            name: str = Field(..., min_length=1)
            price: float = Field(..., gt=0)

        # Valid product
        product = Product(name="Test", price=9.99)
        assert product.name == "Test"

        # Invalid price
        with pytest.raises(Exception):  # Pydantic ValidationError
            Product(name="Test", price=-5.0)

    def test_model_inheritance(self):
        """Test that models can inherit from BaseS3Model."""

        class BaseProduct(BaseS3Model):
            name: str
            price: float

        class DigitalProduct(BaseProduct):
            download_url: str

        product = DigitalProduct(
            name="Software", price=29.99, download_url="https://example.com/download"
        )

        assert product.name == "Software"
        assert product.download_url == "https://example.com/download"
        assert hasattr(product, "id")
        assert hasattr(product, "created_at")

    def test_multiple_models_different_prefixes(self):
        """Test that different models get different S3 prefixes."""
        set_base_s3_path("app/")

        class User(BaseS3Model):
            username: str

        class Product(BaseS3Model):
            name: str

        user_prefix = User.get_s3_prefix()
        product_prefix = Product.get_s3_prefix()

        assert user_prefix != product_prefix
        assert "user" in user_prefix.lower()
        assert "product" in product_prefix.lower()
