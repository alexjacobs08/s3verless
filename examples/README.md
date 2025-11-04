# S3verless Examples

This directory contains practical examples demonstrating how to use S3verless to build serverless applications.

## Examples

All examples demonstrate different features and complexity levels.

### 1. Todo App (`todo_app/`)
**Complexity: ⭐ Beginner**

A simple todo list application demonstrating:
- Basic CRUD operations
- Model definition
- Auto-generated REST API
- Admin interface

**Security**: Public (no authentication)

### 2. Blog Platform (`blog_platform/`)
**Complexity: ⭐⭐⭐ Advanced** ⭐ **Recommended Starting Point**

A complete blogging platform showcasing S3verless's **automatic ownership** and **admin role** features:

**Models**:
- Posts (with automatic ownership)
- Comments (with automatic ownership)  
- Categories (public)

**Security Features**:
- **Default admin account**: Login immediately with `admin` / `Admin123!`
- **Automatic ownership checks**: `_require_ownership = True`
- **Admin bypass**: Users with `is_admin=True` can modify anything
- **Auto-set owner**: `user_id` field automatically set on creation
- **Mixed access**: Categories are public, posts/comments are protected

**What You'll Learn**:
- How to use `_require_ownership` for user-owned content
- How admin roles work and bypass ownership
- How to mix public and protected resources
- JWT authentication with role-based access
- Building a real-world multi-model application

**Perfect for**: Production-ready applications that need user authentication and data ownership

**Quick Start**: Just run `python main.py` and login to `/admin` with `admin` / `Admin123!`

### 3. E-commerce Catalog (`ecommerce/`)
**Complexity: ⭐⭐ Intermediate**

A product catalog system demonstrating:
- Product management with SKUs
- Categories and tags
- Search functionality
- Inventory tracking
- Reviews and ratings

**Security**: Public (no authentication)

### 4. User Authentication (`auth_example/`)
**Complexity: ⭐⭐ Intermediate**

Authentication and authorization example showing:
- User registration and login
- JWT token authentication
- Protected routes
- Token-based access control

**Security**: Demonstrates auth patterns (no real data, focus on auth flow)

## Running the Examples

Each example can be run independently. Navigate to the example directory and follow the README instructions.

### General Setup

1. Install S3verless:
```bash
# Using uv (recommended)
uv pip install s3verless

# Or using pip
pip install s3verless
```

2. Set up your AWS credentials (or use LocalStack for local development):
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
export AWS_BUCKET_NAME=your-bucket
export SECRET_KEY=your-secret-key-for-jwt
```

3. Run the example:
```bash
cd examples/todo_app
uvicorn main:app --reload
```

## Using LocalStack for Local Development

For local testing without AWS:

```bash
# Install LocalStack
uv pip install localstack

# Start LocalStack
localstack start

# Set environment variables
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

## Contributing

Feel free to contribute more examples! Please ensure they:
- Are well-documented
- Include a README with setup instructions
- Demonstrate a specific use case or feature
- Follow best practices

