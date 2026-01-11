"""Tests for seeding module."""

import json
import pytest
from datetime import datetime
from pydantic import EmailStr
from typing import ClassVar

from s3verless.core.base import BaseS3Model
from s3verless.seeding.generator import DataGenerator
from s3verless.seeding.loader import SeedLoader


class SampleProduct(BaseS3Model):
    """Sample model for testing seeding."""

    _plural_name: ClassVar[str] = "products"

    name: str
    description: str
    price: float
    email: str
    phone: str | None = None
    is_active: bool = True
    quantity: int = 0


class TestDataGenerator:
    """Tests for DataGenerator class."""

    def test_init_default_locale(self):
        """Test generator initializes with default locale."""
        gen = DataGenerator()
        assert gen.locale == "en_US"

    def test_init_custom_locale(self):
        """Test generator initializes with custom locale."""
        gen = DataGenerator(locale="de_DE")
        assert gen.locale == "de_DE"

    def test_generate_for_email_field(self):
        """Test generating email field."""
        gen = DataGenerator()
        field_info = SampleProduct.model_fields["email"]
        value = gen.generate_for_field("email", field_info)
        assert value is not None
        assert "@" in str(value)

    def test_generate_for_name_field(self):
        """Test generating name field."""
        gen = DataGenerator()
        field_info = SampleProduct.model_fields["name"]
        value = gen.generate_for_field("name", field_info)
        assert value is not None
        assert isinstance(value, str)
        assert len(value) > 0

    def test_generate_for_description_field(self):
        """Test generating description field."""
        gen = DataGenerator()
        field_info = SampleProduct.model_fields["description"]
        value = gen.generate_for_field("description", field_info)
        assert value is not None
        assert isinstance(value, str)

    def test_generate_for_price_field(self):
        """Test generating price field."""
        gen = DataGenerator()
        field_info = SampleProduct.model_fields["price"]
        value = gen.generate_for_field("price", field_info)
        assert value is not None
        assert isinstance(value, (int, float))
        assert value >= 0

    def test_generate_for_phone_field(self):
        """Test generating phone field."""
        gen = DataGenerator()
        field_info = SampleProduct.model_fields["phone"]
        value = gen.generate_for_field("phone", field_info)
        # Phone can be None due to Optional type
        if value is not None:
            assert isinstance(value, str)

    def test_generate_for_bool_field(self):
        """Test generating boolean field."""
        gen = DataGenerator()
        field_info = SampleProduct.model_fields["is_active"]
        value = gen.generate_for_field("is_active", field_info)
        assert value is not None
        assert isinstance(value, bool)

    def test_generate_for_int_field(self):
        """Test generating integer field."""
        gen = DataGenerator()
        field_info = SampleProduct.model_fields["quantity"]
        value = gen.generate_for_field("quantity", field_info)
        assert value is not None
        assert isinstance(value, int)

    def test_generate_instance(self):
        """Test generating a complete model instance."""
        gen = DataGenerator()
        data = gen.generate_instance(SampleProduct)

        assert "name" in data
        assert "description" in data
        assert "price" in data
        assert "email" in data
        # id, created_at, updated_at should be skipped
        assert "id" not in data
        assert "created_at" not in data
        assert "updated_at" not in data

    def test_generate_multiple_instances(self):
        """Test generating multiple unique instances."""
        gen = DataGenerator()
        instances = [gen.generate_instance(SampleProduct) for _ in range(5)]

        # Each instance should be a valid dict
        for inst in instances:
            assert isinstance(inst, dict)
            assert "name" in inst

        # Names should generally be different (statistically very likely)
        names = [inst["name"] for inst in instances]
        assert len(set(names)) > 1  # At least some should be unique


class TestSeedLoader:
    """Tests for SeedLoader class."""

    def test_load_from_file_list(self, tmp_path):
        """Test loading seed data from JSON file with list."""
        seed_file = tmp_path / "seeds.json"
        seed_data = [
            {"name": "Product 1", "price": 10.0},
            {"name": "Product 2", "price": 20.0},
        ]
        seed_file.write_text(json.dumps(seed_data))

        loaded = SeedLoader.load_from_file(seed_file)

        assert len(loaded) == 2
        assert loaded[0]["name"] == "Product 1"
        assert loaded[1]["name"] == "Product 2"

    def test_load_from_file_single_object(self, tmp_path):
        """Test loading seed data from JSON file with single object."""
        seed_file = tmp_path / "seed.json"
        seed_data = {"name": "Single Product", "price": 15.0}
        seed_file.write_text(json.dumps(seed_data))

        loaded = SeedLoader.load_from_file(seed_file)

        assert len(loaded) == 1
        assert loaded[0]["name"] == "Single Product"

    @pytest.mark.asyncio
    async def test_seed_model(self, mock_s3):
        """Test seeding a model with data."""
        seed_data = [
            {"name": "Test Product", "description": "A test", "price": 10.0, "email": "test@example.com"},
        ]

        count = await SeedLoader.seed_model(
            mock_s3,
            SampleProduct,
            seed_data,
            "test-bucket"
        )

        assert count == 1

    @pytest.mark.asyncio
    async def test_clear_model(self, mock_s3):
        """Test clearing model data."""
        # First seed some data
        seed_data = [
            {"name": "Product 1", "description": "Desc 1", "price": 10.0, "email": "test1@example.com"},
            {"name": "Product 2", "description": "Desc 2", "price": 20.0, "email": "test2@example.com"},
        ]
        await SeedLoader.seed_model(mock_s3, SampleProduct, seed_data, "test-bucket")

        # Then clear
        deleted = await SeedLoader.clear_model(mock_s3, SampleProduct, "test-bucket")

        assert deleted == 2


# Fixtures
@pytest.fixture
def mock_s3():
    """Provide an in-memory S3 mock."""
    from s3verless.testing.mocks import InMemoryS3
    return InMemoryS3()
