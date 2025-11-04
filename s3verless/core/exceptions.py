"""Custom exceptions for S3verless framework."""


class S3verlessError(Exception):
    """Base exception for all S3verless errors."""

    pass


class S3ConnectionError(S3verlessError):
    """Raised when there is an error connecting to S3."""

    pass


class S3OperationError(S3verlessError):
    """Raised when an S3 operation fails."""

    pass


class S3ModelError(S3verlessError):
    """Raised when there is an error with S3 model operations."""

    pass


class S3AuthError(S3verlessError):
    """Raised when there is an authentication/authorization error."""

    pass


class S3ValidationError(S3verlessError):
    """Raised when there is a validation error."""

    pass


# Alias for backwards compatibility
S3verlessException = S3verlessError
