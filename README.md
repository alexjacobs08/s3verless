# S3verless 🚀

[![PyPI version](https://badge.fury.io/py/s3verless.svg)](https://badge.fury.io/py/s3verless)
[![Python Versions](https://img.shields.io/pypi/pyversions/s3verless.svg)](https://pypi.org/project/s3verless/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/alexjacobs08/s3verless/workflows/Tests/badge.svg)](https://github.com/alexjacobs08/s3verless/actions)
[![Development Status](https://img.shields.io/badge/status-alpha-orange.svg)](https://pypi.org/project/s3verless/)

> **📖 [Visit the official website](https://s3verless.org)**

**S3verless** is a Python framework that lets you build complete web applications using only Amazon S3 as your backend. No databases, no servers, no complicated infrastructure - just S3 and your Python code.

## ✨ Features

- 🗄️ **S3 as a Database**: Store all your data as JSON objects in S3
- 🔌 **Drop-in FastAPI Integration**: Automatic REST API generation for your models
- 🎨 **Admin Interface**: Auto-generated admin panel for managing your data
- 🔍 **Advanced Querying**: Filter, sort, paginate, and search your S3 data
- 🔐 **Built-in Auth**: JWT-based authentication with users stored in S3
- 📦 **Zero Config**: Works out of the box with sensible defaults
- 🚀 **Truly Serverless**: Deploy to AWS Lambda or any container platform
- 💰 **Cost-Effective**: Pay only for S3 storage and requests

## 🎯 Why S3verless?

Traditional web applications require multiple services:
- ❌ Database server (RDS, DynamoDB, MongoDB)
- ❌ File storage (S3)
- ❌ Cache layer (Redis, Memcached)  
- ❌ Session storage
- ❌ Complex deployment and scaling

With S3verless:
- ✅ Everything in S3
- ✅ Infinite scalability built-in
- ✅ Simple deployment
- ✅ Minimal operational overhead
- ✅ Perfect for MVPs, prototypes, and small to medium applications

## 🚀 Quick Start

### Installation

```bash
# Using uv (recommended)
uv pip install s3verless

# Or using pip
pip install s3verless
```

### Create Your First Model

```python
from s3verless import BaseS3Model
from pydantic import Field

class Product(BaseS3Model):
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    description: str = ""
    in_stock: bool = True

# That's it! S3verless automatically creates:
# - POST /products
# - GET /products
# - GET /products/{id}
# - PUT /products/{id}
# - DELETE /products/{id}
# - GET /products/search
# - Admin interface at /admin
```

### Create Your App

```python
from s3verless import create_s3verless_app

# Create the FastAPI app with S3 backend
app = create_s3verless_app(
    title="My S3 Store",
    model_packages=["models"],  # Where your models live
    enable_admin=True,
)

# Run with any ASGI server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Configure S3

Create a `.env` file:

```env
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_BUCKET_NAME=my-app-bucket
AWS_DEFAULT_REGION=us-east-1

# For local development with LocalStack
AWS_URL=http://localhost:4566
```

## 📚 Advanced Usage

### Custom API Configuration

```python
class Product(BaseS3Model):
    # Customize API behavior
    _plural_name = "products"        # API endpoint name
    _enable_api = True              # Auto-generate CRUD endpoints
    _enable_admin = True            # Show in admin interface
    _indexes = ["category", "price"] # Fields to index
    _unique_fields = ["sku"]        # Enforce uniqueness
    
    name: str
    sku: str
    category: str
    price: float
```

### Advanced Queries

```python
from s3verless import get_s3_client, query

async def find_products():
    s3 = get_s3_client()
    
    # Filter and sort
    products = await query(Product, s3, "my-bucket").filter(
        category="electronics",
        price__lt=1000,
        in_stock=True
    ).order_by("-created_at").limit(10).all()
    
    # Pagination
    page = await query(Product, s3, "my-bucket").paginate(
        page=1, 
        page_size=20
    )
    
    # Complex queries
    results = await query(Product, s3, "my-bucket").filter(
        name__contains="iPhone"
    ).exclude(
        price__gt=1500
    ).all()
```

### Relationships

```python
import uuid

class Order(BaseS3Model):
    customer_id: uuid.UUID
    items: list[dict]  # Embedded items
    total: float
    
    async def get_customer(self, s3_client):
        """Fetch related customer."""
        return await query(Customer, s3_client, "bucket").get(
            id=self.customer_id
        )
```

### Hooks and Events

```python
from s3verless.core.registry import add_model_hook

async def send_welcome_email(user):
    print(f"Welcome {user.email}!")

# Register a post-creation hook
add_model_hook("User", "post_create", send_welcome_email)
```

## 🔐 Authentication & Authorization

S3verless includes built-in JWT-based authentication with users stored in S3, plus automatic ownership checks and admin roles.

### Basic Authentication

Simple JWT token authentication:

```python
from s3verless.auth.service import S3AuthService
from s3verless.core.settings import S3verlessSettings

settings = S3verlessSettings()
auth_service = S3AuthService(settings)

# Register a new user
user = await auth_service.create_user(
    s3_client=s3_client,
    username="john",
    email="john@example.com",
    password="SecurePass123!",
    full_name="John Doe"
)

# Authenticate and get JWT token
authenticated_user = await auth_service.authenticate_user(
    s3_client=s3_client,
    username="john",
    password="SecurePass123!"
)

# Create access token
token = auth_service.create_access_token(
    data={"sub": authenticated_user.username}
)
```

### Protected Routes

```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = auth_service.decode_token(token)
        username = payload.get("sub")
        user = await auth_service.get_user_by_username(s3_client, username)
        if not user:
            raise HTTPException(status_code=401)
        return user
    except Exception:
        raise HTTPException(status_code=401)

@app.get("/protected")
async def protected_route(user = Depends(get_current_user)):
    return {"message": f"Hello {user.username}"}
```

### Current Limitations

The authentication system uses a **single global secret key** for signing all JWT tokens:

- ✅ Simple and stateless (standard JWT pattern)
- ✅ No database lookups for token validation
- ✅ Works great for most use cases
- ⚠️ Changing the secret invalidates ALL user tokens
- ⚠️ Cannot revoke individual user tokens (tokens valid until expiry)
- ⚠️ No per-user token invalidation (e.g., after password change)

For most applications, this is acceptable. See the [Future Work](#-future-work--roadmap) section for planned improvements.

**Security Best Practices:**
- Use a strong, random `SECRET_KEY` (32+ characters)
- Keep tokens short-lived (15-30 minutes recommended)
- Use HTTPS in production
- Store the secret key securely (environment variables, AWS Secrets Manager)
- Consider implementing token refresh for better UX

See the [auth example](examples/auth_example/) for a complete implementation.

### Automatic Ownership & Admin Roles

Protect resources with automatic ownership checks and admin bypass:

```python
class Post(BaseS3Model):
    _require_ownership = True  # Users can only modify their own posts
    _owner_field = "user_id"   # Field that stores the owner ID
    
    user_id: str  # Automatically set to current user on creation
    title: str
    content: str

# Now automatically:
# ✅ POST /posts/ - Sets user_id to current user
# ✅ PUT /posts/{id} - Only owner (or admin) can update
# ✅ DELETE /posts/{id} - Only owner (or admin) can delete
# ✅ Admins bypass all ownership checks
```

#### Three Levels of Protection

**1. Public (default)** - No authentication required:
```python
class Product(BaseS3Model):
    # No security flags - anyone can CRUD
    name: str
    price: float
```

**2. Auth Required** - Must be logged in:
```python
class SiteSettings(BaseS3Model):
    _require_auth = True  # Any logged-in user can modify
    
    site_name: str
    maintenance_mode: bool
```

**3. Ownership Required** - Must be owner or admin:
```python
class BlogPost(BaseS3Model):
    _require_ownership = True  # Only owner can modify
    _owner_field = "user_id"   # Field containing owner ID
    
    user_id: str  # Auto-set on creation
    title: str
```

#### Admin Users

Users with `is_admin=True` can bypass all ownership checks.

**Default Admin (Development)**:

S3verless automatically creates a default admin account on startup:
- Username: `admin`
- Password: `Admin123!`  
- Can be customized via environment variables

```bash
# Customize default admin (optional)
export DEFAULT_ADMIN_USERNAME=myadmin
export DEFAULT_ADMIN_PASSWORD=SecurePass123!
export DEFAULT_ADMIN_EMAIL=admin@mysite.com

# Disable in production
export CREATE_DEFAULT_ADMIN=false
```

**Programmatic Admin Creation**:

```python
# Create an admin user
admin = await auth_service.create_user(
    s3_client, "admin", "admin@site.com", "SecurePass123!"
)
admin.is_admin = True  # Make them admin
await user_service.update(s3_client, str(admin.id), admin)

# Admin can now:
# - Modify ANY post (even if user_id doesn't match)
# - Delete ANY comment (even if not theirs)
# - Full access to all ownership-protected resources
```

See the [blog platform example](examples/blog_platform/) for a complete implementation.

## 🛠️ CLI Tool

S3verless includes a CLI for common tasks:

```bash
# Create a new project
s3verless init my-app --template ecommerce

# Inspect models
s3verless inspect models.py

# List S3 data
s3verless list-data --bucket my-bucket --prefix products/

# Show version
s3verless version
```

## 🏗️ Architecture

S3verless uses a simple but powerful architecture:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────▶│  S3verless   │────▶│     S3      │
│   Routes    │     │  Data Layer  │     │   Bucket    │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
              ┌─────▼────┐  ┌────▼─────┐
              │  Query   │  │  Auth    │
              │  Engine  │  │  System  │
              └──────────┘  └──────────┘
```

## 🚀 Deployment

### AWS Lambda

```python
# lambda_function.py
from mangum import Mangum
from main import app

handler = Mangum(app)
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Local Development

Use LocalStack for S3 emulation:

```bash
docker run -d -p 4566:4566 localstack/localstack
```

## 📊 Performance Considerations

- **Caching**: S3verless caches frequently accessed objects
- **Indexing**: Use `_indexes` for faster queries
- **Pagination**: Always paginate large datasets
- **Batch Operations**: Use bulk endpoints for multiple operations

## 🧪 Testing

S3verless includes comprehensive tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=s3verless --cov-report=term-missing

# Run specific test file
pytest tests/test_base.py
```

## 📖 Documentation

- **[Official Website](https://s3verless.org)** - Landing page and overview
- **[GitHub Repository](https://github.com/alexjacobs08/s3verless)** - Source code
- **[PyPI Package](https://pypi.org/project/s3verless/)** - Install with pip
- **[Examples](examples/)** - 4 complete example applications
- **[Contributing](CONTRIBUTING.md)** - How to contribute

## 🔮 Future Work & Roadmap

We're actively working on improving S3verless. Here are some planned features:

### Authentication & Security
- **Refresh Tokens**: Implement refresh token pattern for better security
  - Short-lived access tokens (15 min)
  - Long-lived refresh tokens (7 days)
  - Token rotation on refresh
- **Token Versioning**: Per-user token version for selective invalidation
- **Token Blacklist**: Ability to revoke specific tokens
- **Secret Rotation**: Support multiple valid secrets during rotation period
- **OAuth2 Integration**: Social login (Google, GitHub, etc.)
- **Multi-factor Authentication**: 2FA/MFA support

### Performance & Scalability
- **Caching Layer**: Redis/Elasticache integration for hot data
- **Connection Pooling**: Improved S3 connection management
- **Batch Operations**: Optimized bulk insert/update/delete
- **Smart Indexing**: Automatic index suggestions based on query patterns
- **Query Optimization**: Query plan analysis and optimization

### Features
- **Full-Text Search**: Integration with OpenSearch/Elasticsearch
- **File Uploads**: Direct S3 upload with presigned URLs
- **Real-time Subscriptions**: WebSocket support for live updates
- **Backup & Restore**: Automated backup strategies
- **Audit Logging**: Track all data changes
- **GraphQL Support**: Alternative to REST API
- **Database Migration**: Import from/export to traditional databases

### Developer Experience
- **Interactive CLI**: Better model scaffolding and management
- **Type Stubs**: Complete type hints for better IDE support
- **Visual Admin**: Enhanced admin interface with charts
- **Testing Utilities**: Mock S3 helpers and test fixtures
- **Performance Profiling**: Built-in query performance monitoring

Want to contribute to any of these? Check out our [Contributing Guide](CONTRIBUTING.md)!

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/alexjacobs08/s3verless.git
cd s3verless

# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Format and lint
uv run ruff format .
uv run ruff check .
```

## 📝 License

S3verless is MIT licensed. See [LICENSE](LICENSE) for details.


## 🔗 Links

- **Website**: https://s3verless.org
- **PyPI**: https://pypi.org/project/s3verless/
- **GitHub**: https://github.com/alexjacobs08/s3verless
- **Issues**: https://github.com/alexjacobs08/s3verless/issues
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

## 💬 Support

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and discussions

---

**Built with ❤️**
