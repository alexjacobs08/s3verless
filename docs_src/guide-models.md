# Models Guide

Define data models with validation, indexes, and unique constraints.

## Basic Model

All models inherit from `BaseS3Model`:

```python
from s3verless.core.base import BaseS3Model

class Product(BaseS3Model):
    name: str
    price: float
    description: str | None = None
```

Every model automatically gets:
- `id: UUID` - Unique identifier
- `created_at: datetime` - Creation timestamp
- `updated_at: datetime` - Last modification

## Class Configuration

### Plural Name

Controls the API route and S3 prefix:

```python
class Product(BaseS3Model):
    _plural_name = "products"  # API: /products, S3: data/products/
```

Default: lowercase class name.

### Unique Fields

Enforce uniqueness across all instances:

```python
class User(BaseS3Model):
    _unique_fields = ["username", "email"]

    username: str
    email: str
```

Unique validation runs on create and update.

### Indexed Fields

Mark fields for optimized queries:

```python
class Product(BaseS3Model):
    _indexed_fields = ["category", "status"]

    category: str
    status: str
```

### Disable Auto API

Exclude model from auto-generated routes:

```python
class InternalLog(BaseS3Model):
    _enable_api = False

    message: str
    level: str
```

## Field Types

Use standard Python types with Pydantic validation:

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

class Status(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

class Article(BaseS3Model):
    title: str                          # Required string
    content: str | None = None          # Optional string
    views: int = 0                       # Integer with default
    price: Decimal                       # Exact decimal
    rating: float                        # Floating point
    is_featured: bool = False            # Boolean
    tags: list[str] = []                # List of strings
    metadata: dict = {}                  # Dictionary
    status: Status = Status.DRAFT        # Enum
    author_id: UUID                      # UUID reference
    published_at: datetime | None = None # Optional datetime
```

## Validation

Use Pydantic validators:

```python
from pydantic import field_validator, EmailStr

class User(BaseS3Model):
    email: EmailStr  # Built-in email validation
    age: int

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v < 0 or v > 150:
            raise ValueError("Age must be between 0 and 150")
        return v
```

## Computed Properties

Add read-only computed fields:

```python
class Order(BaseS3Model):
    items: list[dict]
    tax_rate: float = 0.1

    @property
    def subtotal(self) -> float:
        return sum(item["price"] * item["quantity"] for item in self.items)

    @property
    def total(self) -> float:
        return self.subtotal * (1 + self.tax_rate)
```

## Model Methods

Add custom methods:

```python
class Task(BaseS3Model):
    title: str
    completed: bool = False
    completed_at: datetime | None = None

    def mark_complete(self) -> None:
        self.completed = True
        self.completed_at = datetime.now(timezone.utc)
        self.touch()  # Update updated_at
```

## S3 Storage

Models are stored as JSON in S3:

```
bucket/
└── data/
    └── products/
        ├── 550e8400-e29b-41d4-a716-446655440000.json
        └── 6ba7b810-9dad-11d1-80b4-00c04fd430c8.json
```

Each file contains:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "name": "Widget",
  "price": 29.99
}
```

## Working with Models

### Create

```python
from s3verless.core.service import S3DataService

service = S3DataService(Product, "my-bucket")

product = await service.create(s3_client, Product(
    name="Widget",
    price=29.99,
))
```

### Read

```python
product = await service.get(s3_client, product.id)
```

### Update

```python
product.price = 24.99
product = await service.update(s3_client, product.id, product)
```

### Delete

```python
await service.delete(s3_client, product.id)
```

### List

```python
products, next_marker = await service.list_by_prefix(s3_client, limit=100)
```

## Best Practices

1. **Keep models small** - S3 reads entire objects, so smaller is faster
2. **Use indexed fields** - Mark frequently filtered fields
3. **Avoid nested objects** - Flatten when possible for better query performance
4. **Use enums for status** - Type safety and validation
5. **Add timestamps** - Already included, but add custom ones as needed
