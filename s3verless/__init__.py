"""S3verless: A framework for building serverless applications using S3 as a backend."""

__version__ = "0.1.1"

# Core components
# Auth components
from s3verless.auth.models import S3User
from s3verless.auth.service import S3AuthService
from s3verless.core.base import BaseS3Model
from s3verless.core.client import S3ClientManager
from s3verless.core.exceptions import S3verlessException
from s3verless.core.query import FilterOperator, QueryResult, S3Query, SortOrder, query
from s3verless.core.service import S3DataService
from s3verless.core.settings import S3verlessSettings

# FastAPI components
from s3verless.fastapi.app import S3verless, create_s3verless_app
from s3verless.fastapi.auth import get_current_user
from s3verless.fastapi.dependencies import get_s3_client, get_s3_service
from s3verless.fastapi.router_generator import generate_crud_router

__all__ = [
    # Core
    "BaseS3Model",
    "S3ClientManager",
    "S3DataService",
    "S3verlessSettings",
    "S3verlessException",
    "S3Query",
    "query",
    "QueryResult",
    "FilterOperator",
    "SortOrder",
    # FastAPI
    "S3verless",
    "create_s3verless_app",
    "get_s3_client",
    "get_s3_service",
    "get_current_user",
    "generate_crud_router",
    # Auth
    "S3User",
    "S3AuthService",
]
