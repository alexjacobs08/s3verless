# S3verless

[![PyPI version](https://badge.fury.io/py/s3verless.svg)](https://badge.fury.io/py/s3verless)
[![Python Versions](https://img.shields.io/pypi/pyversions/s3verless.svg)](https://pypi.org/project/s3verless/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python framework for building web applications using S3 as the database. Define Pydantic models, get automatic REST APIs and an admin interface.

**[Documentation](https://s3verless.org)** | **[PyPI](https://pypi.org/project/s3verless/)** | **[GitHub](https://github.com/alexjacobs08/s3verless)**

## Install

```bash
pip install s3verless
```

## Quick Start

```python
from s3verless import BaseS3Model, create_s3verless_app

class Product(BaseS3Model):
    name: str
    price: float
    in_stock: bool = True

app = create_s3verless_app(
    title="My Store",
    model_packages=["models"],
    enable_admin=True,
)
```

This generates:
- `POST/GET /products` - Create and list
- `GET/PUT/DELETE /products/{id}` - Read, update, delete
- `/admin` - Admin interface

## Configuration

```env
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_BUCKET_NAME=my-bucket
AWS_DEFAULT_REGION=us-east-1

# Local development with LocalStack
AWS_URL=http://localhost:4566
```

## Features

**Models**
```python
class Product(BaseS3Model):
    _plural_name = "products"      # API endpoint
    _indexes = ["category"]        # Indexed fields
    _unique_fields = ["sku"]       # Unique constraints

    name: str
    sku: str
    category: str
```

**Queries**
```python
products = await query(Product, s3, bucket).filter(
    category="electronics",
    price__lt=1000
).order_by("-created_at").limit(10).all()
```

**Authentication**
```python
class Post(BaseS3Model):
    _require_ownership = True
    _owner_field = "user_id"

    user_id: str
    title: str
```

Built-in JWT auth with refresh tokens, token blacklist, and rate limiting.

**Relationships**
```python
from s3verless.core.relationships import has_many, OnDelete

class Author(BaseS3Model):
    name: str
    posts = has_many("Post", foreign_key="author_id", on_delete=OnDelete.CASCADE)
```

**Migrations**
```python
from s3verless.migrations import Migration, AddField

migration = Migration(
    version="001",
    model_name="Product",
    operations=[AddField("category", default="uncategorized")]
)
```

**Caching**
```python
from s3verless.cache import InMemoryCache, LRUCache

cache = LRUCache(max_size=1000, default_ttl=300)
```

**File Uploads**
```python
from s3verless.storage import PresignedUploadService

service = PresignedUploadService(bucket_name="uploads")
url = await service.generate_upload_url(s3, "file.pdf", "application/pdf")
```

**Testing**
```python
from s3verless.testing import InMemoryS3, ModelFactory

s3 = InMemoryS3()
factory = ModelFactory(Product)
product = await factory.create(s3, "test-bucket")
```

## Deployment

**Lambda**
```python
from mangum import Mangum
handler = Mangum(app)
```

**Docker**
```dockerfile
FROM python:3.11-slim
COPY . /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Development

```bash
git clone https://github.com/alexjacobs08/s3verless.git
cd s3verless
pip install -e ".[dev]"
pytest
```

## License

MIT
