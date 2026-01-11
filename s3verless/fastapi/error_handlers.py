"""FastAPI error handlers for S3verless exceptions.

This module provides exception handlers that convert S3verless exceptions
into properly formatted JSON responses with helpful error messages.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from s3verless.core.exceptions import (
    S3verlessError,
    S3ConnectionError,
    S3BucketNotFoundError,
    S3OperationError,
    S3ModelError,
    S3AuthError,
    S3ValidationError,
    S3ConfigurationError,
    S3RateLimitError,
)


async def s3verless_exception_handler(
    request: Request,
    exc: S3verlessError
) -> JSONResponse:
    """Handle S3verless exceptions with helpful error messages.

    Args:
        request: The FastAPI request
        exc: The S3verless exception

    Returns:
        JSONResponse with error details
    """
    # Determine status code based on exception type
    if isinstance(exc, S3ConnectionError):
        status_code = 503
        error_type = "service_unavailable"
    elif isinstance(exc, S3BucketNotFoundError):
        status_code = 503
        error_type = "configuration_error"
    elif isinstance(exc, S3AuthError):
        status_code = 401
        error_type = getattr(exc, "error_code", "authentication_error")
    elif isinstance(exc, S3ValidationError):
        status_code = 400
        error_type = "validation_error"
    elif isinstance(exc, S3ModelError):
        status_code = 400
        error_type = "model_error"
    elif isinstance(exc, S3ConfigurationError):
        status_code = 500
        error_type = "configuration_error"
    elif isinstance(exc, S3RateLimitError):
        status_code = 429
        error_type = "rate_limit_exceeded"
    elif isinstance(exc, S3OperationError):
        status_code = 500
        error_type = "operation_error"
    else:
        status_code = 500
        error_type = "internal_error"

    content = {
        "error": error_type,
        "message": exc.message,
    }

    # Include hint if available (but only in debug mode for production safety)
    if exc.hint:
        content["hint"] = exc.hint

    # Add specific fields for certain exception types
    if isinstance(exc, S3ValidationError) and exc.field:
        content["field"] = exc.field
    if isinstance(exc, S3RateLimitError) and exc.retry_after:
        content["retry_after"] = exc.retry_after

    headers = {}
    if isinstance(exc, S3RateLimitError) and exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    if isinstance(exc, S3AuthError):
        headers["WWW-Authenticate"] = "Bearer"

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers if headers else None,
    )


async def validation_exception_handler(
    request: Request,
    exc: ValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Args:
        request: The FastAPI request
        exc: The Pydantic ValidationError

    Returns:
        JSONResponse with validation error details
    """
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": errors,
        },
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: The FastAPI request
        exc: The exception

    Returns:
        JSONResponse with generic error message
    """
    # In production, don't expose internal error details
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


def register_error_handlers(app: FastAPI, include_generic: bool = False) -> None:
    """Register all S3verless error handlers with a FastAPI app.

    Args:
        app: The FastAPI application
        include_generic: Whether to include a generic handler for all exceptions
    """
    # Register S3verless-specific handlers
    app.add_exception_handler(S3verlessError, s3verless_exception_handler)
    app.add_exception_handler(S3ConnectionError, s3verless_exception_handler)
    app.add_exception_handler(S3BucketNotFoundError, s3verless_exception_handler)
    app.add_exception_handler(S3OperationError, s3verless_exception_handler)
    app.add_exception_handler(S3ModelError, s3verless_exception_handler)
    app.add_exception_handler(S3AuthError, s3verless_exception_handler)
    app.add_exception_handler(S3ValidationError, s3verless_exception_handler)
    app.add_exception_handler(S3ConfigurationError, s3verless_exception_handler)
    app.add_exception_handler(S3RateLimitError, s3verless_exception_handler)

    # Register Pydantic validation handler
    app.add_exception_handler(ValidationError, validation_exception_handler)

    # Optionally register generic handler
    if include_generic:
        app.add_exception_handler(Exception, generic_exception_handler)
