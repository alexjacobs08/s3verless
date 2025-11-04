"""Tests for model registry."""


from s3verless.core.base import BaseS3Model
from s3verless.core.registry import (
    get_all_metadata,
    get_all_models,
    get_base_s3_path,
    get_model_metadata,
    get_model_s3_prefix,
    set_base_s3_path,
)


class TestRegistry:
    """Tests for model registry functions."""

    def test_set_and_get_base_path(self):
        """Test setting and getting base S3 path."""
        set_base_s3_path("test-app/")
        assert get_base_s3_path() == "test-app/"

        set_base_s3_path("another-path/")
        assert get_base_s3_path() == "another-path/"

    def test_base_path_trailing_slash(self):
        """Test that base path always has trailing slash."""
        set_base_s3_path("myapp")
        assert get_base_s3_path() == "myapp/"

        set_base_s3_path("myapp/")
        assert get_base_s3_path() == "myapp/"

    def test_register_model(self):
        """Test model registration."""

        class TestModel(BaseS3Model):
            name: str

        # Model should auto-register via __init_subclass__
        metadata = get_model_metadata("TestModel")
        assert metadata is not None
        assert metadata.model_class == TestModel

    def test_model_metadata(self):
        """Test model metadata extraction."""

        class Product(BaseS3Model):
            _plural_name = "products"
            _api_prefix = "/api/products"
            _indexes = ["category", "price"]
            _unique_fields = ["sku"]

            name: str
            sku: str
            category: str
            price: float

        metadata = get_model_metadata("Product")

        assert metadata.plural_name == "products"
        assert metadata.api_prefix == "/api/products"
        assert "category" in metadata.indexes
        assert "price" in metadata.indexes
        assert "sku" in metadata.unique_fields

    def test_model_metadata_defaults(self):
        """Test that default metadata is generated."""

        class SimpleModel(BaseS3Model):
            name: str

        metadata = get_model_metadata("SimpleModel")

        assert metadata is not None
        # Should auto-generate plural name
        assert "simple" in metadata.plural_name.lower()
        # Should auto-generate API prefix
        assert "/simple" in metadata.api_prefix.lower()

    def test_get_all_models(self):
        """Test getting all registered models."""

        class Model1(BaseS3Model):
            name: str

        class Model2(BaseS3Model):
            title: str

        all_models = get_all_models()

        assert "Model1" in all_models
        assert "Model2" in all_models
        assert all_models["Model1"] == Model1
        assert all_models["Model2"] == Model2

    def test_get_all_metadata(self):
        """Test getting all model metadata."""

        class Product(BaseS3Model):
            _plural_name = "products"
            name: str

        class Order(BaseS3Model):
            _plural_name = "orders"
            total: float

        all_metadata = get_all_metadata()

        assert "Product" in all_metadata
        assert "Order" in all_metadata
        assert all_metadata["Product"].plural_name == "products"
        assert all_metadata["Order"].plural_name == "orders"

    def test_get_model_s3_prefix(self):
        """Test getting S3 prefix for a model."""
        set_base_s3_path("app-data/")

        class Article(BaseS3Model):
            title: str

        prefix = get_model_s3_prefix(Article)

        assert prefix.startswith("app-data/")
        assert "article" in prefix.lower()
        assert prefix.endswith("/")

    def test_custom_plural_name(self):
        """Test custom plural name."""

        class Person(BaseS3Model):
            _plural_name = "people"
            name: str

        metadata = get_model_metadata("Person")
        prefix = get_model_s3_prefix(Person)

        assert metadata.plural_name == "people"
        assert "people" in prefix

    def test_enable_disable_api(self):
        """Test enabling/disabling API for models."""

        class PublicModel(BaseS3Model):
            _enable_api = True
            name: str

        class PrivateModel(BaseS3Model):
            _enable_api = False
            name: str

        public_meta = get_model_metadata("PublicModel")
        private_meta = get_model_metadata("PrivateModel")

        assert public_meta.enable_api is True
        assert private_meta.enable_api is False

    def test_enable_disable_admin(self):
        """Test enabling/disabling admin interface."""

        class VisibleModel(BaseS3Model):
            _enable_admin = True
            name: str

        class HiddenModel(BaseS3Model):
            _enable_admin = False
            name: str

        visible_meta = get_model_metadata("VisibleModel")
        hidden_meta = get_model_metadata("HiddenModel")

        assert visible_meta.enable_admin is True
        assert hidden_meta.enable_admin is False

    def test_model_with_indexes(self):
        """Test model with indexed fields."""

        class IndexedModel(BaseS3Model):
            _indexes = ["email", "created_at", "status"]

            name: str
            email: str
            status: str

        metadata = get_model_metadata("IndexedModel")

        assert "email" in metadata.indexes
        assert "created_at" in metadata.indexes
        assert "status" in metadata.indexes

    def test_model_with_unique_fields(self):
        """Test model with unique field constraints."""

        class UniqueModel(BaseS3Model):
            _unique_fields = ["email", "username"]

            username: str
            email: str

        metadata = get_model_metadata("UniqueModel")

        assert "email" in metadata.unique_fields
        assert "username" in metadata.unique_fields

    def test_nonexistent_model_metadata(self):
        """Test getting metadata for non-existent model."""
        metadata = get_model_metadata("NonExistentModel")
        assert metadata is None
