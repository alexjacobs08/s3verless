# S3verless API Reference

Complete API documentation for all public classes and functions.

## Core Module

### BaseS3Model

Base class for all S3-stored models. Inherit from this to create your data models.

```python
from s3verless.core.base import BaseS3Model

class Product(BaseS3Model):
    _plural_name = "products"
    _unique_fields = ["sku"]
    _indexed_fields = ["category", "price"]

    name: str
    sku: str
    price: float
    category: str
```

**Class Variables:**
- `_plural_name: str` - Plural name for API routes (default: lowercase class name)
- `_unique_fields: list[str]` - Fields that must be unique across all instances
- `_indexed_fields: list[str]` - Fields to index for faster queries
- `_enable_api: bool` - Whether to auto-generate CRUD API (default: True)

**Instance Attributes:**
- `id: UUID` - Auto-generated unique identifier
- `created_at: datetime` - Creation timestamp (UTC)
- `updated_at: datetime` - Last update timestamp (UTC)

**Methods:**

```python
@classmethod
def get_s3_prefix(cls) -> str:
    """Get the S3 prefix for this model."""

@classmethod
def get_s3_key(cls, object_id: UUID) -> str:
    """Get the full S3 key for an object."""

def touch(self) -> None:
    """Update the updated_at timestamp."""

@property
def s3_key(self) -> str:
    """Get the S3 key for this instance."""
```

---

### S3DataService

Generic service for CRUD operations on S3-stored models.

```python
from s3verless.core.service import S3DataService

service = S3DataService(Product, "my-bucket")
```

**Constructor:**
```python
S3DataService(model: Type[T], bucket_name: str)
```

**Methods:**

```python
async def get(self, s3_client, obj_id: UUID) -> T | None:
    """Retrieve an object by ID."""

async def create(self, s3_client, data: BaseModel) -> T:
    """Create a new object. Validates unique fields."""

async def update(self, s3_client, obj_id: UUID, update_data: BaseModel) -> T | None:
    """Update an existing object."""

async def delete(self, s3_client, obj_id: UUID) -> bool:
    """Delete an object by ID."""

async def exists(self, s3_client, obj_id: UUID) -> bool:
    """Check if an object exists."""

async def list_by_prefix(
    self, s3_client, limit: int = 100, marker: str | None = None
) -> tuple[list[T], str | None]:
    """List objects with pagination."""

async def paginate(
    self, s3_client, page: int = 1, page_size: int = 20
) -> dict:
    """List objects with pagination metadata."""
```

---

### Query

Fluent query builder for filtering and sorting S3 data.

```python
from s3verless.core.query import Query

results = await (
    Query(Product, s3_client, "my-bucket")
    .filter(category="electronics")
    .filter(price__gt=100)
    .order_by("-price")
    .limit(10)
    .all()
)
```

**Constructor:**
```python
Query(model_class: Type[T], s3_client, bucket_name: str)
```

**Filter Operators:**
- `field=value` - Exact match
- `field__eq=value` - Equal
- `field__ne=value` - Not equal
- `field__gt=value` - Greater than
- `field__gte=value` - Greater than or equal
- `field__lt=value` - Less than
- `field__lte=value` - Less than or equal
- `field__in=[values]` - In list
- `field__nin=[values]` - Not in list
- `field__contains=value` - String contains (case-sensitive)
- `field__icontains=value` - String contains (case-insensitive)
- `field__startswith=value` - String starts with
- `field__endswith=value` - String ends with
- `field__isnull=True/False` - Is null/not null

**Methods:**

```python
def filter(self, **kwargs) -> Query[T]:
    """Add filter conditions."""

def exclude(self, **kwargs) -> Query[T]:
    """Exclude items matching conditions."""

def order_by(self, field: str) -> Query[T]:
    """Sort results. Prefix with '-' for descending."""

def limit(self, n: int) -> Query[T]:
    """Limit number of results."""

def offset(self, n: int) -> Query[T]:
    """Skip first n results."""

def select(self, *fields: str) -> Query[T]:
    """Select specific fields only."""

def prefetch_related(self, *relations: str) -> Query[T]:
    """Prefetch related objects."""

async def all(self) -> list[T]:
    """Execute query and return all results."""

async def first(self) -> T | None:
    """Return first result or None."""

async def get(self) -> T:
    """Return exactly one result. Raises if 0 or >1."""

async def count(self) -> int:
    """Count matching objects."""

async def exists(self) -> bool:
    """Check if any matching objects exist."""

async def paginate(self, page: int = 1, page_size: int = 20) -> QueryResult[T]:
    """Get paginated results with metadata."""
```

---

### S3ClientManager

Singleton manager for S3 client instances with connection pooling.

```python
from s3verless.core.client import S3ClientManager

manager = S3ClientManager(settings)
```

**Methods:**

```python
def get_sync_client(self) -> BaseClient:
    """Get a synchronous boto3 S3 client."""

@asynccontextmanager
async def get_async_client(self) -> AsyncIterator[AioBaseClient]:
    """Get an async S3 client from the pool."""

def stats(self) -> dict:
    """Get client pool statistics."""
```

---

## Auth Module

### S3AuthService

Complete authentication service with JWT tokens and user management.

```python
from s3verless.auth.service import S3AuthService

auth = S3AuthService(settings)
```

**Constructor:**
```python
S3AuthService(
    settings: S3verlessSettings | None = None,
    secret_key: str | None = None,
    algorithm: str = "HS256",
    access_token_expire_minutes: int = 30,
    refresh_token_expire_days: int = 7,
    bucket_name: str | None = None,
)
```

**User Management:**

```python
async def create_user(
    self, s3_client, username: str, email: str, password: str,
    full_name: str | None = None
) -> S3User:
    """Create a new user."""

async def get_user_by_username(self, s3_client, username: str) -> S3User | None:
    """Find user by username."""

async def get_user_by_email(self, s3_client, email: str) -> S3User | None:
    """Find user by email."""

async def authenticate_user(
    self, s3_client, username: str, password: str
) -> S3User | None:
    """Authenticate with username/password."""
```

**Token Management:**

```python
async def create_token_pair(
    self, s3_client, user: S3User,
    device_info: str | None = None,
    ip_address: str | None = None,
) -> dict:
    """Create access and refresh token pair."""

async def refresh_access_token(self, s3_client, refresh_token: str) -> dict:
    """Get new access token using refresh token."""

async def revoke_refresh_token(self, s3_client, refresh_token: str) -> bool:
    """Revoke a specific refresh token."""

async def revoke_all_user_tokens(self, s3_client, user_id: UUID) -> int:
    """Revoke all tokens for a user."""

async def cleanup_expired_tokens(self, s3_client) -> int:
    """Remove expired/revoked tokens."""
```

**Password Utilities:**

```python
def get_password_hash(self, password: str) -> str:
    """Hash a password using bcrypt."""

def verify_password(self, plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""

def validate_password(self, password: str) -> tuple[bool, str]:
    """Validate password strength."""
```

---

### TokenBlacklist

In-memory + S3 token blacklist for immediate revocation.

```python
from s3verless.auth.blacklist import TokenBlacklist

blacklist = TokenBlacklist(bucket_name)
```

**Methods:**

```python
async def add(self, s3_client, token_jti: str, expires_at: datetime) -> None:
    """Add token to blacklist."""

async def is_blacklisted(self, s3_client, token_jti: str) -> bool:
    """Check if token is blacklisted."""

async def cleanup(self, s3_client) -> int:
    """Remove expired entries."""
```

---

### RateLimiter

Per-endpoint rate limiting with configurable limits.

```python
from s3verless.auth.rate_limit import RateLimiter

limiter = RateLimiter(
    limits={"login": RateLimit(10, 60)},
    trusted_proxies=["10.0.0.1"],
    trust_x_forwarded_for=True,
)
```

**Methods:**

```python
async def is_rate_limited(
    self, request, endpoint: str | None = None
) -> tuple[bool, dict]:
    """Check if request is rate limited."""

def get_rate_limit_headers(self, info: dict) -> dict:
    """Get rate limit headers for response."""
```

---

## Cache Module

### CacheBackend (Abstract)

Base class for cache implementations.

```python
async def get(self, key: str) -> Any | None
async def set(self, key: str, value: Any, ttl: int | None = None) -> None
async def delete(self, key: str) -> bool
async def exists(self, key: str) -> bool
async def clear(self) -> None
async def delete_pattern(self, pattern: str) -> int
```

### InMemoryCache

Simple in-memory cache with TTL and size limits.

```python
from s3verless.cache.memory import InMemoryCache

cache = InMemoryCache(default_ttl=300, max_size=1000)
```

### LRUCache

LRU eviction cache with hit rate tracking.

```python
from s3verless.cache.memory import LRUCache

cache = LRUCache(max_size=1000, default_ttl=300)
```

### CompositeCache

Multi-tier cache that chains backends.

```python
from s3verless.cache.composite import CompositeCache

cache = CompositeCache([
    LRUCache(max_size=100, default_ttl=60),
    InMemoryCache(max_size=1000, default_ttl=300),
])
```

---

## Storage Module

### PresignedUploadService

Generate presigned URLs for direct S3 uploads.

```python
from s3verless.storage.uploads import PresignedUploadService, UploadConfig

config = UploadConfig(
    max_file_size=10 * 1024 * 1024,
    allowed_content_types=["image/jpeg", "image/png"],
    expiration_seconds=3600,
)
service = PresignedUploadService("my-bucket", config)
```

**Methods:**

```python
async def generate_upload_url(
    self, s3_client, filename: str,
    content_type: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Generate presigned URL for upload."""

async def generate_download_url(
    self, s3_client, s3_key: str,
    filename: str | None = None,
    expires_in: int | None = None,
) -> str:
    """Generate presigned URL for download."""

async def confirm_upload(
    self, s3_client, s3_key: str, uploaded_by: UUID | None = None
) -> UploadedFile | None:
    """Confirm upload and create file record."""

async def delete_file(self, s3_client, s3_key: str) -> bool:
    """Delete a file from S3."""
```

---

## FastAPI Module

### S3verless

Main application class with auto-configuration.

```python
from s3verless.fastapi.app import S3verless

app_builder = S3verless(
    settings=settings,
    title="My API",
    enable_admin=True,
    model_packages=["myapp.models"],
)
app = app_builder.create_app()
```

**Constructor:**
```python
S3verless(
    settings: S3verlessSettings | None = None,
    title: str = "S3verless API",
    description: str = "API powered by S3verless",
    version: str = "1.0.0",
    enable_admin: bool = True,
    model_packages: list[str] | None = None,
    auto_discover: bool = True,
)
```

---

## Migrations Module

### Migration

Define data migrations.

```python
from s3verless.migrations.base import Migration

migration = Migration(
    version="0001",
    model_name="Product",
    description="Add discount field",
    apply=lambda data: {**data, "discount": 0},
    rollback=lambda data: {k: v for k, v in data.items() if k != "discount"},
    reversible=True,
)
```

### MigrationRunner

Execute migrations.

```python
from s3verless.migrations.runner import MigrationRunner

runner = MigrationRunner(s3_client, "my-bucket", Path("./migrations"))
results = await runner.run_pending()
```

---

## Testing Module

### InMemoryS3

Mock S3 client for testing.

```python
from s3verless.testing.mocks import InMemoryS3, mock_s3_client

# Direct usage
s3 = InMemoryS3()
await s3.put_object(Bucket="test", Key="data.json", Body=b'{}')

# Context manager
with mock_s3_client() as s3:
    await s3.create_bucket(Bucket="test")
```

---

## Settings

### S3verlessSettings

Configuration via environment variables or direct instantiation.

```python
from s3verless.core.settings import S3verlessSettings

settings = S3verlessSettings(
    aws_bucket_name="my-bucket",
    aws_region="us-east-1",
    secret_key="your-jwt-secret",
)
```

**Environment Variables:**
- `AWS_BUCKET_NAME` - S3 bucket name
- `AWS_REGION` - AWS region
- `AWS_ACCESS_KEY_ID` - AWS credentials
- `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `AWS_ENDPOINT_URL` - Custom endpoint (LocalStack)
- `SECRET_KEY` - JWT signing key
- `ALGORITHM` - JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiry (default: 30)
- `S3_BASE_PATH` - Base path prefix in bucket
