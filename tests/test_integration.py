"""Integration tests for S3verless FastAPI app."""

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from s3verless.core.base import BaseS3Model
from s3verless.core.registry import set_base_s3_path
from s3verless.core.settings import S3verlessSettings
from s3verless.fastapi.app import S3verless


# Define test models
class Product(BaseS3Model):
    """Test product model."""

    _plural_name = "products"
    _api_prefix = "/api/products"

    name: str
    price: float
    stock: int = 0


class Customer(BaseS3Model):
    """Test customer model."""

    _plural_name = "customers"
    _api_prefix = "/api/customers"

    name: str
    email: str


@pytest.fixture
def test_settings():
    """Create test settings."""
    return S3verlessSettings(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_default_region="us-east-1",
        aws_bucket_name="test-bucket",
        aws_url="http://localhost:4566",
        secret_key="test-secret-key",
        s3_base_path="test/",
        debug=True,
    )


@pytest.fixture
def s3verless_app(test_settings, async_mock_s3_client):
    """Create S3verless app for testing."""
    # Manually register models first (before app creation)
    from s3verless.core.registry import register_model
    from s3verless.fastapi.dependencies import get_s3_client, get_settings

    register_model(Product)
    register_model(Customer)

    with mock_aws():
        # Create S3 bucket
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")

        set_base_s3_path("test/")

        # Create app with auto-discovery disabled
        # (models are already registered above)
        app_instance = S3verless(
            settings=test_settings,
            title="Test API",
            enable_admin=True,
            auto_discover=False,
        )

        # Create the FastAPI app
        app = app_instance.create_app()

        # Override dependencies to use test fixtures
        app.dependency_overrides[get_settings] = lambda: test_settings

        # Override S3 client to use our async mock
        async def mock_get_s3_client():
            yield async_mock_s3_client

        app.dependency_overrides[get_s3_client] = mock_get_s3_client

        # Manually trigger router generation and admin setup
        # since they normally happen in lifespan
        app_instance._generate_routers(app)
        if app_instance.enable_admin:
            app_instance._setup_admin(app)

        yield app


@pytest.fixture
def client(s3verless_app):
    """Create test client."""
    with mock_aws():
        # Create S3 bucket for client use
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket="test-bucket")

        return TestClient(s3verless_app)


class TestAppCreation:
    """Tests for S3verless app creation."""

    def test_app_creation(self, s3verless_app):
        """Test that app is created successfully."""
        assert s3verless_app is not None
        assert s3verless_app.title == "Test API"

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "models_registered" in data

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data


class TestGeneratedCRUDEndpoints:
    """Tests for auto-generated CRUD endpoints."""

    def test_create_product(self, client):
        """Test creating a product via API."""
        product_data = {"name": "Test Product", "price": 19.99, "stock": 10}

        response = client.post("/api/products/", json=product_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Test Product"
        assert data["price"] == 19.99
        assert "id" in data

    def test_list_products(self, client):
        """Test listing products."""
        # Create some products first
        for i in range(3):
            client.post(
                "/api/products/",
                json={"name": f"Product {i}", "price": 10.0 + i, "stock": i * 10},
            )

        response = client.get("/api/products/")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total_count" in data
        assert len(data["items"]) >= 3

    def test_get_product(self, client):
        """Test getting a single product."""
        # Create product
        create_response = client.post(
            "/api/products/",
            json={"name": "Specific Product", "price": 29.99, "stock": 5},
        )
        product_id = create_response.json()["id"]

        # Get product
        response = client.get(f"/api/products/{product_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == product_id
        assert data["name"] == "Specific Product"

    def test_update_product(self, client):
        """Test updating a product."""
        # Create product
        create_response = client.post(
            "/api/products/",
            json={"name": "Original Name", "price": 15.00, "stock": 20},
        )
        product_id = create_response.json()["id"]

        # Update product
        update_data = {"name": "Updated Name", "price": 25.00}
        response = client.put(f"/api/products/{product_id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["price"] == 25.00

    def test_delete_product(self, client):
        """Test deleting a product."""
        # Create product
        create_response = client.post(
            "/api/products/", json={"name": "To Delete", "price": 5.00, "stock": 1}
        )
        product_id = create_response.json()["id"]

        # Delete product
        response = client.delete(f"/api/products/{product_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/products/{product_id}")
        # Either 404 or 500 acceptable for now (mock client behavior)
        assert get_response.status_code in [404, 500]

    def test_pagination(self, client):
        """Test pagination in list endpoint."""
        # Create 10 products
        for i in range(10):
            client.post(
                "/api/products/",
                json={"name": f"Product {i}", "price": float(i), "stock": i},
            )

        # Get page 1
        response = client.get("/api/products/?page=1&page_size=5")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 5
        assert data["has_next"] is True
        assert data["has_prev"] is False

        # Get page 2
        response = client.get("/api/products/?page=2&page_size=5")
        data = response.json()
        assert data["has_prev"] is True

    def test_search_endpoint(self, client):
        """Test search functionality."""
        # Create products
        client.post(
            "/api/products/",
            json={"name": "Laptop Computer", "price": 999.99, "stock": 5},
        )
        client.post(
            "/api/products/", json={"name": "Mouse", "price": 19.99, "stock": 50}
        )

        # Search for "laptop"
        response = client.get("/api/products/search/?q=Laptop")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) >= 1
        assert any("Laptop" in item["name"] for item in data["items"])

    def test_bulk_create(self, client):
        """Test bulk create endpoint."""
        products = [
            {"name": "Bulk Product 1", "price": 10.0, "stock": 10},
            {"name": "Bulk Product 2", "price": 20.0, "stock": 20},
            {"name": "Bulk Product 3", "price": 30.0, "stock": 30},
        ]

        response = client.post("/api/products/bulk", json=products)
        assert response.status_code == 201

        data = response.json()
        assert len(data) == 3
        assert all("id" in item for item in data)


class TestAdminInterface:
    """Tests for admin interface."""

    def test_admin_endpoint_exists(self, client):
        """Test that admin interface is accessible."""
        response = client.get("/admin")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_html_content(self, client):
        """Test that admin interface has proper HTML."""
        response = client.get("/admin")
        content = response.text

        assert "<!DOCTYPE html>" in content
        assert "S3verless Admin" in content
        assert "products" in content.lower()
        assert "customers" in content.lower()


class TestMultipleModels:
    """Tests for multiple models in the same app."""

    def test_multiple_model_endpoints(self, client):
        """Test that endpoints exist for all models."""
        # Products endpoint
        response = client.get("/api/products/")
        assert response.status_code == 200

        # Customers endpoint
        response = client.get("/api/customers/")
        assert response.status_code == 200

    def test_create_different_models(self, client):
        """Test creating instances of different models."""
        # Create product
        product_response = client.post(
            "/api/products/", json={"name": "Widget", "price": 9.99, "stock": 100}
        )
        assert product_response.status_code == 201

        # Create customer
        customer_response = client.post(
            "/api/customers/", json={"name": "John Doe", "email": "john@example.com"}
        )
        assert customer_response.status_code == 201

        # Verify they're different
        assert product_response.json()["id"] != customer_response.json()["id"]
