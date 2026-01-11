# Getting Started with S3verless

Build serverless APIs using S3 as your database in minutes.

## Installation

```bash
pip install s3verless
```

## Quick Start

### 1. Define a Model

```python
# models.py
from s3verless.core.base import BaseS3Model

class Task(BaseS3Model):
    _plural_name = "tasks"

    title: str
    completed: bool = False
    priority: int = 0
```

### 2. Create the Application

```python
# main.py
from s3verless.fastapi.app import S3verless
from s3verless.core.settings import S3verlessSettings

settings = S3verlessSettings(
    aws_bucket_name="my-app-bucket",
    aws_region="us-east-1",
)

app_builder = S3verless(
    settings=settings,
    title="Task API",
    model_packages=["models"],
)

app = app_builder.create_app()
```

### 3. Run the API

```bash
uvicorn main:app --reload
```

Your API is now available at `http://localhost:8000` with:
- `GET /tasks` - List all tasks
- `POST /tasks` - Create a task
- `GET /tasks/{id}` - Get a task
- `PUT /tasks/{id}` - Update a task
- `DELETE /tasks/{id}` - Delete a task
- `GET /admin` - Admin interface

## Local Development with LocalStack

For local development without AWS costs:

```bash
# Start LocalStack
docker run -d -p 4566:4566 localstack/localstack

# Configure S3verless
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_BUCKET_NAME=local-bucket
```

## Configuration

S3verless uses environment variables or direct settings:

```python
settings = S3verlessSettings(
    # Required
    aws_bucket_name="my-bucket",

    # AWS credentials (or use IAM roles)
    aws_access_key_id="...",
    aws_secret_access_key="...",
    aws_region="us-east-1",

    # LocalStack/MinIO
    aws_endpoint_url="http://localhost:4566",

    # Auth settings
    secret_key="your-secret-key",
    access_token_expire_minutes=30,

    # Admin user
    create_default_admin=True,
    default_admin_username="admin",
    default_admin_password="changeme",
    default_admin_email="admin@example.com",
)
```

## Environment Variables

```bash
# AWS Configuration
AWS_BUCKET_NAME=my-bucket
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_ENDPOINT_URL=http://localhost:4566  # For LocalStack

# Auth
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Data
S3_BASE_PATH=data/

# Admin
CREATE_DEFAULT_ADMIN=true
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=changeme
DEFAULT_ADMIN_EMAIL=admin@example.com
```

## Project Structure

Recommended project layout:

```
myapp/
├── main.py           # FastAPI app
├── models/
│   ├── __init__.py
│   ├── task.py       # Task model
│   └── user.py       # Custom user fields
├── routers/
│   └── custom.py     # Custom endpoints
├── seeds/
│   └── tasks.json    # Seed data
└── migrations/
    └── 0001_add_priority.py
```

## Next Steps

- [Models Guide](guide-models.md) - Define models with indexes and validation
- [Queries Guide](guide-queries.md) - Filter, sort, and paginate data
- [Auth Guide](guide-auth.md) - Add authentication and authorization
- [Deployment Guide](guide-deployment.md) - Deploy to AWS Lambda
