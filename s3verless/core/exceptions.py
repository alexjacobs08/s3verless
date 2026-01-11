"""Custom exceptions for S3verless framework.

This module provides a hierarchy of exceptions with helpful error messages
to make debugging easier for developers.
"""


class S3verlessError(Exception):
    """Base exception for all S3verless errors.

    All S3verless exceptions inherit from this class, making it easy
    to catch all framework-specific errors.
    """

    def __init__(self, message: str, hint: str | None = None):
        """Initialize the exception.

        Args:
            message: The error message
            hint: Optional hint for resolving the error
        """
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\nHint: {self.hint}"
        return self.message


class S3ConnectionError(S3verlessError):
    """Raised when there is an error connecting to S3.

    This exception wraps underlying connection errors with helpful
    context about what might be wrong.
    """

    def __init__(
        self,
        message: str | None = None,
        original_error: Exception | None = None,
        endpoint: str | None = None,
    ):
        """Initialize the connection error.

        Args:
            message: Custom error message (optional)
            original_error: The original exception that caused this error
            endpoint: The S3 endpoint URL being connected to
        """
        self.original_error = original_error
        self.endpoint = endpoint

        if message:
            final_message = message
            hint = None
        elif original_error:
            final_message, hint = self._format_error(original_error, endpoint)
        else:
            final_message = "Failed to connect to S3"
            hint = "Check your AWS credentials and network connection."

        super().__init__(final_message, hint)

    def _format_error(
        self, error: Exception, endpoint: str | None
    ) -> tuple[str, str | None]:
        """Format the error message based on the underlying error."""
        error_str = str(error)

        if "Could not connect" in error_str or "Connection refused" in error_str:
            if endpoint and "localhost" in endpoint:
                return (
                    f"Could not connect to S3 at {endpoint}",
                    "If using LocalStack, ensure it's running: docker run -d -p 4566:4566 localstack/localstack",
                )
            return (
                f"Could not connect to S3 at {endpoint or 'AWS'}",
                "Check your network connection and AWS endpoint configuration.",
            )

        if "InvalidAccessKeyId" in error_str:
            return (
                "Invalid AWS access key ID",
                "Check your AWS_ACCESS_KEY_ID environment variable.",
            )

        if "SignatureDoesNotMatch" in error_str:
            return (
                "AWS signature mismatch",
                "Check your AWS_SECRET_ACCESS_KEY environment variable.",
            )

        if "ExpiredToken" in error_str:
            return (
                "AWS credentials have expired",
                "Refresh your AWS credentials or generate new access keys.",
            )

        if "UnauthorizedAccess" in error_str or "AccessDenied" in error_str:
            return (
                "Access denied to AWS resources",
                "Check your IAM permissions for S3 access.",
            )

        return (f"S3 connection error: {error}", None)


class S3BucketNotFoundError(S3verlessError):
    """Raised when the configured bucket doesn't exist."""

    def __init__(self, bucket_name: str):
        """Initialize the bucket not found error.

        Args:
            bucket_name: The bucket that was not found
        """
        self.bucket_name = bucket_name
        super().__init__(
            f"Bucket '{bucket_name}' not found",
            f"Create the bucket with: aws s3 mb s3://{bucket_name}\n"
            "Or check the AWS_BUCKET_NAME environment variable.",
        )


class S3OperationError(S3verlessError):
    """Raised when an S3 operation fails."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        key: str | None = None,
        original_error: Exception | None = None,
    ):
        """Initialize the operation error.

        Args:
            message: The error message
            operation: The S3 operation that failed (e.g., 'get_object')
            key: The S3 key involved in the operation
            original_error: The original exception
        """
        self.operation = operation
        self.key = key
        self.original_error = original_error

        hint = None
        if "NoSuchKey" in message:
            hint = f"The object at key '{key}' does not exist."
        elif "NoSuchBucket" in message:
            hint = "The specified bucket does not exist."
        elif "AccessDenied" in message:
            hint = "Check your IAM permissions for this operation."

        super().__init__(message, hint)


class S3ModelError(S3verlessError):
    """Raised when there is an error with S3 model operations."""

    def __init__(
        self,
        message: str,
        model_name: str | None = None,
        field_name: str | None = None,
    ):
        """Initialize the model error.

        Args:
            message: The error message
            model_name: The model class name
            field_name: The field involved in the error
        """
        self.model_name = model_name
        self.field_name = field_name

        hint = None
        if "unique constraint" in message.lower():
            hint = f"The value for '{field_name}' already exists. Choose a different value."
        elif "validation" in message.lower():
            hint = "Check the field values match the model's type requirements."

        super().__init__(message, hint)


class S3AuthError(S3verlessError):
    """Raised when there is an authentication/authorization error."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
    ):
        """Initialize the auth error.

        Args:
            message: The error message
            error_code: Optional error code for client handling
        """
        self.error_code = error_code or "authentication_error"

        hint = None
        if "token" in message.lower():
            hint = "Ensure you're sending a valid JWT token in the Authorization header."
        elif "password" in message.lower():
            hint = "Check your username and password."
        elif "permission" in message.lower() or "forbidden" in message.lower():
            hint = "You don't have permission to perform this action."

        super().__init__(message, hint)


class S3ValidationError(S3verlessError):
    """Raised when there is a validation error."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: str | None = None,
    ):
        """Initialize the validation error.

        Args:
            message: The error message
            field: The field that failed validation
            value: The invalid value (don't include sensitive data!)
        """
        self.field = field
        self.value = value

        hint = None
        if field:
            hint = f"Check the value for field '{field}'."

        super().__init__(message, hint)


class S3ConfigurationError(S3verlessError):
    """Raised when S3verless configuration is invalid."""

    def __init__(
        self,
        message: str | None = None,
        missing_fields: list[str] | None = None,
    ):
        """Initialize the configuration error.

        Args:
            message: Custom error message
            missing_fields: List of missing configuration fields
        """
        self.missing_fields = missing_fields or []

        if missing_fields:
            fields_str = ", ".join(missing_fields)
            message = f"Missing required configuration: {fields_str}"
            hint = "Set these as environment variables or in your .env file."
        else:
            hint = "Check your S3verless configuration."

        super().__init__(message or "Invalid S3verless configuration", hint)


class S3RateLimitError(S3verlessError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ):
        """Initialize the rate limit error.

        Args:
            message: The error message
            retry_after: Seconds until the rate limit resets
        """
        self.retry_after = retry_after

        hint = None
        if retry_after:
            hint = f"Try again in {retry_after} seconds."
        else:
            hint = "Please wait before making more requests."

        super().__init__(message, hint)


# Alias for backwards compatibility
S3verlessException = S3verlessError
