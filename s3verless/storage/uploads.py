"""Presigned URL upload handling for S3verless."""

import mimetypes
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar, List

from s3verless.core.base import BaseS3Model


@dataclass
class UploadConfig:
    """Configuration for file uploads.

    Attributes:
        max_file_size: Maximum file size in bytes (default: 10MB)
        allowed_content_types: List of allowed MIME types (None for any)
        upload_prefix: S3 key prefix for uploads
        expiration_seconds: How long presigned URLs are valid
    """

    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_content_types: List[str] | None = None
    upload_prefix: str = "uploads/"
    expiration_seconds: int = 3600


class UploadedFile(BaseS3Model):
    """Model representing an uploaded file.

    This model tracks metadata about uploaded files and can be linked
    to other models via the file_id field.
    """

    _plural_name: ClassVar[str] = "uploaded_files"
    _enable_api: ClassVar[bool] = False  # Custom upload endpoints instead

    filename: str
    content_type: str
    size: int
    s3_key: str
    uploaded_by: uuid.UUID | None = None
    is_public: bool = False


class PresignedUploadService:
    """Service for generating presigned URLs for direct S3 uploads.

    Presigned URLs allow clients to upload files directly to S3 without
    routing through your server, reducing bandwidth and latency.

    Example:
        service = PresignedUploadService(bucket_name, config)

        # Get presigned URL for upload
        url_data = await service.generate_upload_url(
            s3_client, "image.jpg", "image/jpeg"
        )

        # Client uploads directly to S3 using url_data
        # ...

        # Confirm upload and create record
        file_record = await service.confirm_upload(
            s3_client, url_data["key"], user_id
        )
    """

    def __init__(
        self,
        bucket_name: str,
        config: UploadConfig | None = None,
    ):
        """Initialize the upload service.

        Args:
            bucket_name: S3 bucket name
            config: Upload configuration
        """
        self.bucket_name = bucket_name
        self.config = config or UploadConfig()

    def _generate_key(self, filename: str) -> str:
        """Generate a unique S3 key for an upload.

        Args:
            filename: Original filename

        Returns:
            Unique S3 key
        """
        # Generate unique ID
        file_id = uuid.uuid4()

        # Get file extension
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()

        # Organize by date
        date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")

        return f"{self.config.upload_prefix}{date_prefix}/{file_id}{ext}"

    def _validate_content_type(self, content_type: str) -> bool:
        """Validate that the content type is allowed.

        Args:
            content_type: MIME type to validate

        Returns:
            True if allowed, False otherwise
        """
        if self.config.allowed_content_types is None:
            return True
        return content_type in self.config.allowed_content_types

    async def generate_upload_url(
        self,
        s3_client,
        filename: str,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Generate a presigned URL for uploading a file.

        Args:
            s3_client: The S3 client to use
            filename: Original filename
            content_type: MIME type (auto-detected if not provided)
            metadata: Optional metadata to attach to the upload

        Returns:
            Dictionary with:
                - url: The presigned URL
                - key: The S3 key
                - fields: Form fields for POST upload
                - expires_in: URL expiration in seconds

        Raises:
            ValueError: If content type is not allowed
        """
        # Auto-detect content type if not provided
        if content_type is None:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # Validate content type
        if not self._validate_content_type(content_type):
            raise ValueError(
                f"Content type '{content_type}' is not allowed. "
                f"Allowed types: {self.config.allowed_content_types}"
            )

        # Generate unique key
        s3_key = self._generate_key(filename)

        # Build conditions for presigned POST
        conditions = [
            {"bucket": self.bucket_name},
            {"key": s3_key},
            {"Content-Type": content_type},
            ["content-length-range", 1, self.config.max_file_size],
        ]

        # Add metadata conditions
        fields = {
            "Content-Type": content_type,
        }
        if metadata:
            for key, value in metadata.items():
                meta_key = f"x-amz-meta-{key}"
                conditions.append({meta_key: value})
                fields[meta_key] = value

        # Generate presigned POST
        try:
            presigned = await s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=s3_key,
                Conditions=conditions,
                Fields=fields,
                ExpiresIn=self.config.expiration_seconds,
            )
        except Exception:
            # Fallback for clients that don't support presigned POST
            presigned = {
                "url": f"https://{self.bucket_name}.s3.amazonaws.com",
                "fields": {"key": s3_key, **fields},
            }

        return {
            "url": presigned["url"],
            "key": s3_key,
            "fields": presigned["fields"],
            "expires_in": self.config.expiration_seconds,
            "max_size": self.config.max_file_size,
        }

    async def generate_download_url(
        self,
        s3_client,
        s3_key: str,
        filename: str | None = None,
        expires_in: int | None = None,
    ) -> str:
        """Generate a presigned URL for downloading a file.

        Args:
            s3_client: The S3 client to use
            s3_key: The S3 key of the file
            filename: Filename to suggest for download
            expires_in: URL expiration in seconds

        Returns:
            The presigned download URL
        """
        params = {
            "Bucket": self.bucket_name,
            "Key": s3_key,
        }

        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        return await s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in or self.config.expiration_seconds,
        )

    async def confirm_upload(
        self,
        s3_client,
        s3_key: str,
        uploaded_by: uuid.UUID | None = None,
    ) -> UploadedFile | None:
        """Confirm an upload and create a file record.

        Call this after the client has uploaded to S3 to verify the upload
        succeeded and create a tracking record.

        Args:
            s3_client: The S3 client to use
            s3_key: The S3 key that was uploaded
            uploaded_by: User ID who uploaded the file

        Returns:
            UploadedFile record if upload exists, None otherwise
        """
        try:
            # Check if object exists and get metadata
            response = await s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )

            # Extract filename from key
            filename = s3_key.rsplit("/", 1)[-1]

            # Create file record
            from s3verless.core.service import S3DataService

            file_record = UploadedFile(
                filename=filename,
                content_type=response.get("ContentType", "application/octet-stream"),
                size=response.get("ContentLength", 0),
                s3_key=s3_key,
                uploaded_by=uploaded_by,
            )

            service = S3DataService(UploadedFile, self.bucket_name)
            return await service.create(s3_client, file_record)

        except Exception:
            return None

    async def delete_file(
        self,
        s3_client,
        s3_key: str,
    ) -> bool:
        """Delete a file from S3.

        Args:
            s3_client: The S3 client to use
            s3_key: The S3 key to delete

        Returns:
            True if deleted successfully
        """
        try:
            await s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return True
        except Exception:
            return False
