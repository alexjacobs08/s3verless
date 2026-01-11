"""S3verless: A framework for building serverless applications using S3 as a backend."""

__version__ = "0.2.0"

# Core components
from s3verless.core.base import BaseS3Model
from s3verless.core.client import S3ClientManager, PoolConfig
from s3verless.core.exceptions import (
    S3verlessException,
    S3verlessError,
    S3ConnectionError,
    S3OperationError,
    S3ModelError,
    S3AuthError,
    S3ValidationError,
    S3ConfigurationError,
    S3RateLimitError,
    S3BucketNotFoundError,
)
from s3verless.core.query import FilterOperator, QueryResult, S3Query, SortOrder, query
from s3verless.core.service import S3DataService
from s3verless.core.settings import S3verlessSettings
from s3verless.core.relationships import (
    Relationship,
    RelationType,
    OnDelete,
    foreign_key,
    has_many,
    has_one,
)

# Auth components
from s3verless.auth.models import S3User, RefreshToken
from s3verless.auth.service import S3AuthService
from s3verless.auth.blacklist import TokenBlacklist, get_blacklist
from s3verless.auth.rate_limit import RateLimiter, RateLimitConfig, rate_limit

# FastAPI components
from s3verless.fastapi.app import S3verless, create_s3verless_app
from s3verless.fastapi.auth import get_current_user
from s3verless.fastapi.dependencies import get_s3_client, get_s3_service
from s3verless.fastapi.router_generator import generate_crud_router
from s3verless.fastapi.error_handlers import register_error_handlers

# Cache components
from s3verless.cache import (
    CacheBackend,
    InMemoryCache,
    LRUCache,
    CompositeCache,
    CacheKeyBuilder,
)

# Storage components
from s3verless.storage import PresignedUploadService, UploadConfig

# Migration components
from s3verless.migrations import (
    Migration,
    MigrationOperation,
    MigrationRunner,
    AddField,
    RemoveField,
    RenameField,
    TransformField,
)

# Seeding components
from s3verless.seeding import DataGenerator, SeedLoader

__all__ = [
    # Version
    "__version__",
    # Core
    "BaseS3Model",
    "S3ClientManager",
    "PoolConfig",
    "S3DataService",
    "S3verlessSettings",
    "S3verlessException",
    "S3verlessError",
    "S3ConnectionError",
    "S3OperationError",
    "S3ModelError",
    "S3AuthError",
    "S3ValidationError",
    "S3ConfigurationError",
    "S3RateLimitError",
    "S3BucketNotFoundError",
    "S3Query",
    "query",
    "QueryResult",
    "FilterOperator",
    "SortOrder",
    # Relationships
    "Relationship",
    "RelationType",
    "OnDelete",
    "foreign_key",
    "has_many",
    "has_one",
    # FastAPI
    "S3verless",
    "create_s3verless_app",
    "get_s3_client",
    "get_s3_service",
    "get_current_user",
    "generate_crud_router",
    "register_error_handlers",
    # Auth
    "S3User",
    "RefreshToken",
    "S3AuthService",
    "TokenBlacklist",
    "get_blacklist",
    "RateLimiter",
    "RateLimitConfig",
    "rate_limit",
    # Cache
    "CacheBackend",
    "InMemoryCache",
    "LRUCache",
    "CompositeCache",
    "CacheKeyBuilder",
    # Storage
    "PresignedUploadService",
    "UploadConfig",
    # Migrations
    "Migration",
    "MigrationOperation",
    "MigrationRunner",
    "AddField",
    "RemoveField",
    "RenameField",
    "TransformField",
    # Seeding
    "DataGenerator",
    "SeedLoader",
]
