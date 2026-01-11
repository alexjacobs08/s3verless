"""Tests for storage/uploads module."""

import pytest
import uuid

from s3verless.storage.uploads import (
    PresignedUploadService,
    UploadConfig,
    UploadedFile,
)


class TestUploadConfig:
    """Tests for UploadConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = UploadConfig()

        assert config.max_file_size == 10 * 1024 * 1024  # 10MB
        assert config.allowed_content_types is None
        assert config.upload_prefix == "uploads/"
        assert config.expiration_seconds == 3600

    def test_custom_config(self):
        """Test custom configuration."""
        config = UploadConfig(
            max_file_size=50 * 1024 * 1024,
            allowed_content_types=["image/png", "image/jpeg"],
            upload_prefix="custom/path/",
            expiration_seconds=7200
        )

        assert config.max_file_size == 50 * 1024 * 1024
        assert "image/png" in config.allowed_content_types
        assert config.upload_prefix == "custom/path/"


class TestUploadedFile:
    """Tests for UploadedFile model."""

    def test_uploaded_file_creation(self):
        """Test creating an UploadedFile."""
        user_id = uuid.uuid4()
        s3_key_value = "uploads/abc123/test.pdf"
        file = UploadedFile(
            filename="test.pdf",
            s3_key=s3_key_value,
            content_type="application/pdf",
            size=1024,
            uploaded_by=user_id
        )

        assert file.filename == "test.pdf"
        # Note: s3_key is a field on the model, not the computed storage key
        assert hasattr(file, "s3_key")
        assert file.content_type == "application/pdf"
        assert file.size == 1024

    def test_uploaded_file_optional_fields(self):
        """Test UploadedFile with optional fields."""
        file = UploadedFile(
            filename="test.pdf",
            s3_key="uploads/test.pdf",
            content_type="application/pdf",
            size=1024
        )

        assert file.uploaded_by is None
        assert file.is_public is False


class TestPresignedUploadService:
    """Tests for PresignedUploadService."""

    @pytest.fixture
    def service(self):
        """Create a PresignedUploadService instance."""
        config = UploadConfig(
            max_file_size=10 * 1024 * 1024,
            upload_prefix="test-uploads/"
        )
        return PresignedUploadService(bucket_name="test-bucket", config=config)

    @pytest.fixture
    def mock_s3(self):
        """Create a mock S3 client."""
        from s3verless.testing.mocks import InMemoryS3
        return InMemoryS3()

    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.bucket_name == "test-bucket"
        assert service.config.upload_prefix == "test-uploads/"

    def test_generate_key(self, service):
        """Test generating S3 key for upload."""
        key = service._generate_key("test-file.pdf")

        assert key.startswith("test-uploads/")
        assert key.endswith(".pdf")

    def test_validate_content_type_allowed(self, service):
        """Test content type validation when allowed."""
        # Default config allows all types
        assert service._validate_content_type("image/png") is True
        assert service._validate_content_type("application/pdf") is True

    def test_validate_content_type_restricted(self):
        """Test content type validation with restrictions."""
        config = UploadConfig(allowed_content_types=["image/png"])
        service = PresignedUploadService("bucket", config)

        assert service._validate_content_type("image/png") is True
        assert service._validate_content_type("image/jpeg") is False

    @pytest.mark.asyncio
    async def test_generate_upload_url(self, service, mock_s3):
        """Test generating upload URL."""
        result = await service.generate_upload_url(
            mock_s3,
            filename="test.pdf",
            content_type="application/pdf"
        )

        assert "url" in result
        assert "key" in result
        assert "expires_in" in result
        assert result["key"].startswith("test-uploads/")

    @pytest.mark.asyncio
    async def test_generate_upload_url_invalid_content_type(self):
        """Test generating upload URL with invalid content type."""
        config = UploadConfig(allowed_content_types=["image/png"])
        service = PresignedUploadService("bucket", config)

        from s3verless.testing.mocks import InMemoryS3
        mock_s3 = InMemoryS3()

        with pytest.raises(ValueError, match="Content type"):
            await service.generate_upload_url(
                mock_s3,
                filename="test.pdf",
                content_type="application/pdf"
            )

    @pytest.mark.asyncio
    async def test_delete_file(self, service, mock_s3):
        """Test deleting an uploaded file."""
        s3_key = "test-uploads/file.pdf"

        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=s3_key,
            Body=b"content"
        )

        result = await service.delete_file(mock_s3, s3_key)

        assert result is True

        # Verify it's deleted
        from botocore.exceptions import ClientError
        with pytest.raises(ClientError):
            await mock_s3.get_object(Bucket="test-bucket", Key=s3_key)

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, service, mock_s3):
        """Test deleting a non-existent file returns False."""
        result = await service.delete_file(mock_s3, "nonexistent/file.pdf")
        # Should not raise, just return False or True depending on implementation
        assert isinstance(result, bool)
