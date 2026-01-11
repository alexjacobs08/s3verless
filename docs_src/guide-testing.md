# Testing Guide

Test your S3verless applications without external dependencies.

## In-Memory S3 Mock

S3verless provides `InMemoryS3`, a fully async-compatible mock S3 client:

```python
from s3verless.testing.mocks import InMemoryS3

s3 = InMemoryS3()

# Use like a real S3 client
await s3.create_bucket(Bucket="test-bucket")
await s3.put_object(Bucket="test-bucket", Key="data.json", Body=b'{"id": 1}')
response = await s3.get_object(Bucket="test-bucket", Key="data.json")
data = await response["Body"].read()
```

## Context Manager

```python
from s3verless.testing.mocks import mock_s3_client

async def test_something():
    with mock_s3_client() as s3:
        await s3.create_bucket(Bucket="test")
        # Test code...
    # Mock is automatically cleared
```

## Pytest Fixtures

### Basic Fixture

```python
import pytest
from s3verless.testing.mocks import InMemoryS3

@pytest.fixture
def s3_client():
    """Provide a fresh mock S3 client for each test."""
    s3 = InMemoryS3()
    yield s3
    s3.clear()

@pytest.fixture
async def bucket(s3_client):
    """Create a test bucket."""
    await s3_client.create_bucket(Bucket="test-bucket")
    return "test-bucket"
```

### Complete Test Setup

```python
import pytest
from s3verless.core.base import BaseS3Model
from s3verless.core.service import S3DataService
from s3verless.core.registry import set_base_s3_path
from s3verless.testing.mocks import InMemoryS3

class Product(BaseS3Model):
    _plural_name = "products"
    name: str
    price: float

@pytest.fixture
def s3_client():
    s3 = InMemoryS3()
    yield s3
    s3.clear()

@pytest.fixture
async def setup(s3_client):
    set_base_s3_path("test/")
    await s3_client.create_bucket(Bucket="test-bucket")
    return {
        "s3_client": s3_client,
        "bucket": "test-bucket",
        "service": S3DataService(Product, "test-bucket"),
    }

@pytest.mark.asyncio
async def test_create_product(setup):
    s3_client = setup["s3_client"]
    service = setup["service"]

    product = await service.create(
        s3_client,
        Product(name="Widget", price=29.99)
    )

    assert product.name == "Widget"
    assert product.id is not None
```

## Testing CRUD Operations

```python
@pytest.mark.asyncio
async def test_crud_operations(setup):
    s3 = setup["s3_client"]
    service = setup["service"]

    # Create
    product = await service.create(s3, Product(name="Widget", price=10.00))
    assert product.id is not None

    # Read
    fetched = await service.get(s3, product.id)
    assert fetched.name == "Widget"

    # Update
    fetched.price = 15.00
    updated = await service.update(s3, product.id, fetched)
    assert updated.price == 15.00

    # Delete
    deleted = await service.delete(s3, product.id)
    assert deleted is True

    # Verify deletion
    fetched = await service.get(s3, product.id)
    assert fetched is None
```

## Testing Queries

```python
from s3verless.core.query import Query

@pytest.mark.asyncio
async def test_query_filter(setup):
    s3 = setup["s3_client"]
    service = setup["service"]
    bucket = setup["bucket"]

    # Create test data
    await service.create(s3, Product(name="Widget A", price=10.00))
    await service.create(s3, Product(name="Widget B", price=20.00))
    await service.create(s3, Product(name="Gadget", price=30.00))

    # Test filter
    results = await (
        Query(Product, s3, bucket)
        .filter(name__startswith="Widget")
        .all()
    )
    assert len(results) == 2

    # Test comparison
    results = await (
        Query(Product, s3, bucket)
        .filter(price__gte=20.00)
        .all()
    )
    assert len(results) == 2
```

## Testing Authentication

```python
from s3verless.auth.service import S3AuthService
from s3verless.core.settings import S3verlessSettings

@pytest.fixture
def auth_service():
    settings = S3verlessSettings(
        aws_bucket_name="test-bucket",
        secret_key="test-secret-key-32-characters-long",
    )
    return S3AuthService(settings)

@pytest.mark.asyncio
async def test_user_registration(s3_client, auth_service):
    await s3_client.create_bucket(Bucket="test-bucket")

    user = await auth_service.create_user(
        s3_client,
        username="testuser",
        email="test@example.com",
        password="SecurePass123!",
    )

    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.hashed_password != "SecurePass123!"

@pytest.mark.asyncio
async def test_authentication(s3_client, auth_service):
    await s3_client.create_bucket(Bucket="test-bucket")

    # Create user
    await auth_service.create_user(
        s3_client, "testuser", "test@example.com", "SecurePass123!"
    )

    # Valid login
    user = await auth_service.authenticate_user(
        s3_client, "testuser", "SecurePass123!"
    )
    assert user is not None

    # Invalid password
    user = await auth_service.authenticate_user(
        s3_client, "testuser", "wrongpassword"
    )
    assert user is None
```

## Testing FastAPI Endpoints

```python
from fastapi.testclient import TestClient
from httpx import AsyncClient

@pytest.fixture
def app(s3_client):
    """Create test app with mock S3."""
    from myapp.main import create_app

    app = create_app()
    app.state.s3_client = s3_client
    return app

@pytest.mark.asyncio
async def test_create_product_endpoint(app, s3_client):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/products",
            json={"name": "Widget", "price": 29.99},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Widget"
    assert "id" in data
```

## Testing Migrations

```python
from s3verless.migrations.base import Migration
from s3verless.migrations.runner import MigrationRunner

@pytest.mark.asyncio
async def test_migration(s3_client):
    await s3_client.create_bucket(Bucket="test-bucket")

    # Create initial data
    await s3_client.put_object(
        Bucket="test-bucket",
        Key="test/products/123.json",
        Body=b'{"id": "123", "name": "Widget"}',
    )

    # Define migration
    migration = Migration(
        version="0001",
        model_name="Product",
        description="Add price field",
        apply=lambda d: {**d, "price": 0.0},
        reversible=True,
    )

    runner = MigrationRunner(s3_client, "test-bucket")
    runner.register(migration)

    # Run migration
    results = await runner.run_pending()
    assert len(results) == 1
    assert results[0]["objects_transformed"] == 1

    # Verify data was migrated
    response = await s3_client.get_object(
        Bucket="test-bucket",
        Key="test/products/123.json",
    )
    data = await response["Body"].read()
    assert b'"price": 0.0' in data
```

## Test Data Helpers

### Seed Data

```python
from s3verless.seeding.loader import SeedLoader

@pytest.mark.asyncio
async def test_with_seed_data(s3_client):
    await s3_client.create_bucket(Bucket="test-bucket")

    # Seed from list
    await SeedLoader.seed_model(
        s3_client,
        Product,
        [
            {"name": "Widget A", "price": 10.00},
            {"name": "Widget B", "price": 20.00},
        ],
        "test-bucket",
    )

    # Verify
    service = S3DataService(Product, "test-bucket")
    products, _ = await service.list_by_prefix(s3_client)
    assert len(products) == 2
```

### Factory Pattern

```python
import factory
from uuid import uuid4

class ProductFactory:
    @staticmethod
    def build(**kwargs):
        defaults = {
            "name": f"Product {uuid4().hex[:6]}",
            "price": 9.99,
        }
        return Product(**{**defaults, **kwargs})

    @staticmethod
    async def create(s3_client, service, **kwargs):
        product = ProductFactory.build(**kwargs)
        return await service.create(s3_client, product)
```

## Best Practices

1. **Use fixtures** - Share setup code across tests
2. **Isolate tests** - Clear mock between tests
3. **Test edge cases** - Empty results, validation errors
4. **Test async properly** - Use `pytest.mark.asyncio`
5. **Mock external services** - Not just S3, but any external dependency
6. **Test error paths** - Ensure proper error handling
7. **Keep tests fast** - In-memory mock enables fast iteration
