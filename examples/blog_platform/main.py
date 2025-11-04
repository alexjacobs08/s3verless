"""
Blog Platform Example with Automatic Ownership & Admin

This example demonstrates:
- Automatic ownership checks (_require_ownership)
- Admin role with bypass permissions
- User registration and JWT authentication
- Mixed public/protected endpoints
- Complete blogging platform
"""

from datetime import datetime
from enum import Enum
from typing import ClassVar

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from s3verless import BaseS3Model, create_s3verless_app
from s3verless.auth.service import S3AuthService
from s3verless.core.settings import S3verlessSettings
from s3verless.fastapi.dependencies import get_s3_client


class PostStatus(str, Enum):
    """Blog post status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Post(BaseS3Model):
    """Blog post with automatic ownership protection.

    Features:
    - Users can only modify their own posts
    - Admins can modify any post
    - user_id is automatically set to current user on creation
    """

    _plural_name = "posts"
    _api_prefix = "/api/posts"
    _require_ownership: ClassVar[bool] = True  # ← Automatic ownership!
    _owner_field: ClassVar[str] = "user_id"
    _indexes = ["user_id", "status", "category"]

    user_id: str  # Automatically set on creation
    author_name: str
    title: str
    slug: str
    content: str
    excerpt: str | None = None
    category: str
    tags: list[str] = []
    status: PostStatus = PostStatus.DRAFT
    published_at: datetime | None = None
    views: int = 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "author_name": "John Doe",
                "title": "Getting Started with S3verless",
                "slug": "getting-started-with-s3verless",
                "content": "S3verless is a powerful framework...",
                "excerpt": "Learn how to build serverless apps",
                "category": "Tutorial",
                "tags": ["s3", "serverless", "python"],
                "status": "draft",
            }
        }
    }


class Comment(BaseS3Model):
    """Comment with ownership - users can only edit their own comments.

    Admins can moderate any comment.
    """

    _plural_name = "comments"
    _api_prefix = "/api/comments"
    _require_ownership: ClassVar[bool] = True
    _owner_field: ClassVar[str] = "user_id"
    _indexes = ["user_id", "post_id"]

    user_id: str  # Automatically set
    user_name: str
    post_id: str
    post_title: str
    content: str
    is_approved: bool = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_name": "Jane Smith",
                "post_id": "post-123",
                "post_title": "My Blog Post",
                "content": "Great article!",
                "is_approved": False,
            }
        }
    }


class Category(BaseS3Model):
    """Blog category - public, no ownership."""

    _plural_name = "categories"
    _api_prefix = "/api/categories"

    name: str
    slug: str
    description: str | None = None
    post_count: int = 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Tutorials",
                "slug": "tutorials",
                "description": "Step-by-step guides",
                "post_count": 0,
            }
        }
    }


# Pydantic models for auth
class UserRegister(BaseModel):
    """User registration request."""

    username: str
    email: EmailStr
    password: str
    full_name: str
    is_admin: bool = False


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str


# Create the FastAPI app
settings = S3verlessSettings(
    aws_bucket_name="blog-platform-bucket",
    secret_key="dev-secret-key-change-in-production",
)

app = create_s3verless_app(
    settings=settings,
    title="Blog Platform API",
    description="Full-featured blog with automatic ownership and admin roles",
    version="1.0.0",
    enable_admin=True,
)

# Initialize auth service
auth_service = S3AuthService(settings)


# Auth endpoints
@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, s3_client=Depends(get_s3_client)):
    """Register a new user."""
    try:
        user = await auth_service.create_user(
            s3_client=s3_client,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
        )

        # Set admin status if requested
        # In production, only existing admins should be able to create new admins
        if user_data.is_admin:
            user.is_admin = True
            from s3verless.auth.models import S3User
            from s3verless.core.service import S3DataService

            user_service = S3DataService(S3User, settings.aws_bucket_name)
            await user_service.update(s3_client, str(user.id), user)

        return {
            "message": "User registered successfully",
            "username": user.username,
            "is_admin": user.is_admin,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), s3_client=Depends(get_s3_client)
):
    """Login and get JWT token."""
    user = await auth_service.authenticate_user(
        s3_client=s3_client, username=form_data.username, password=form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.create_access_token(
        data={"sub": user.username, "is_admin": user.is_admin}
    )

    return Token(access_token=access_token, token_type="bearer")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Blog Platform API",
        "version": "1.0.0",
        "features": [
            "Automatic ownership checks for posts and comments",
            "Admin users can bypass all ownership restrictions",
            "JWT authentication",
            "Auto-generated CRUD APIs",
            "Admin interface at /admin",
        ],
        "security": {
            "posts": "Ownership required (only author can modify, or admin)",
            "comments": "Ownership required (only commenter can modify, or admin)",
            "categories": "Public (anyone can CRUD)",
        },
        "endpoints": {
            "register": "/register",
            "login": "/token",
            "docs": "/docs",
            "admin": "/admin",
            "posts": "/api/posts",
            "comments": "/api/comments",
            "categories": "/api/categories",
        },
    }


if __name__ == "__main__":
    import uvicorn

    print("\n🚀 Blog Platform Starting...")
    print("📖 Visit http://localhost:8000/docs for API documentation")
    print("🎨 Visit http://localhost:8000/admin for admin interface")
    print("\n⚠️  Make sure LocalStack is running or AWS credentials are configured!")
    print("   Quick start: docker run -d -p 4566:4566 localstack/localstack\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
