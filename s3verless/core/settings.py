"""Settings management for S3verless."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class S3verlessSettings(BaseSettings):
    """Settings for S3verless framework.

    This class handles configuration for AWS credentials, S3 settings,
    authentication settings, and other framework options. It uses Pydantic's
    settings management to load values from environment variables.

    Attributes:
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        aws_default_region: AWS region (default: us-east-1)
        aws_bucket_name: S3 bucket name
        aws_url: Optional custom S3 endpoint URL (for LocalStack, etc.)
        aws_retry_attempts: Number of retry attempts for S3 operations
        secret_key: Secret key for JWT token signing
        algorithm: JWT algorithm to use
        access_token_expire_minutes: Token expiration time in minutes
        debug: Enable debug mode
        app_name: Application name
        s3_base_path: Base path prefix for all S3 objects
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # AWS Credentials
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_default_region: str = "us-east-1"
    aws_bucket_name: str
    aws_url: str | None = None
    aws_retry_attempts: int = 3

    # Authentication Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Default Admin Account (for development/setup)
    default_admin_username: str | None = "admin"
    default_admin_password: str | None = "Admin123!"  # Meets validation requirements
    default_admin_email: str | None = "admin@example.com"
    create_default_admin: bool = True  # Set to False in production

    # Framework Settings
    debug: bool = False
    app_name: str = "S3verless App"
    s3_base_path: str = ""

    def get_s3_config(self) -> dict:
        """Get S3 configuration as a dictionary.

        Returns:
            Dictionary of S3 configuration values
        """
        return {
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
            "aws_default_region": self.aws_default_region,
            "aws_bucket_name": self.aws_bucket_name,
            "aws_url": self.aws_url,
            "aws_retry_attempts": self.aws_retry_attempts,
        }

    def get_auth_config(self) -> dict:
        """Get authentication configuration as a dictionary.

        Returns:
            Dictionary of authentication configuration values
        """
        return {
            "secret_key": self.secret_key,
            "algorithm": self.algorithm,
            "access_token_expire_minutes": self.access_token_expire_minutes,
        }
