"""Tests for S3AuthService."""

import json
from datetime import datetime, timedelta

import pytest
from jose import jwt

from s3verless.auth.service import S3AuthService
from s3verless.core.exceptions import S3verlessException
from s3verless.core.settings import S3verlessSettings


@pytest.fixture
def test_settings():
    """Create test settings for auth."""
    return S3verlessSettings(
        aws_bucket_name="test-bucket",
        secret_key="test-secret-key-for-jwt",
        algorithm="HS256",
        access_token_expire_minutes=30,
    )


@pytest.fixture
async def s3_client(async_mock_s3_client):
    """Create S3 mock client."""
    return async_mock_s3_client


@pytest.fixture
def auth_service(test_settings):
    """Create auth service instance."""
    return S3AuthService(test_settings)


class TestS3AuthService:
    """Tests for S3AuthService."""

    @pytest.mark.asyncio
    async def test_create_user(self, auth_service, s3_client):
        """Test creating a new user."""
        user = await auth_service.create_user(
            s3_client,
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            full_name="Test User",
        )

        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.hashed_password != "SecurePass123!"
        assert user.hashed_password.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_create_duplicate_username(self, auth_service, s3_client):
        """Test that duplicate usernames are not allowed."""
        # Create first user
        await auth_service.create_user(
            s3_client,
            username="testuser",
            email="test1@example.com",
            password="SecurePass123!",
        )

        # Try to create with same username
        with pytest.raises(S3verlessException, match="Username.*already exists"):
            await auth_service.create_user(
                s3_client,
                username="testuser",
                email="test2@example.com",
                password="SecurePass456!",
            )

    @pytest.mark.asyncio
    async def test_create_duplicate_email(self, auth_service, s3_client):
        """Test that duplicate emails are not allowed."""
        # Create first user
        await auth_service.create_user(
            s3_client,
            username="user1",
            email="test@example.com",
            password="SecurePass123!",
        )

        # Try to create with same email
        with pytest.raises(S3verlessException, match="Email.*already exists"):
            await auth_service.create_user(
                s3_client,
                username="user2",
                email="test@example.com",
                password="SecurePass456!",
            )

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, s3_client):
        """Test successful user authentication."""
        # Create user
        await auth_service.create_user(
            s3_client,
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

        # Authenticate
        user = await auth_service.authenticate_user(
            s3_client, "testuser", "SecurePass123!"
        )

        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, auth_service, s3_client):
        """Test authentication with wrong password."""
        # Create user
        await auth_service.create_user(
            s3_client,
            username="testuser",
            email="test@example.com",
            password="CorrectPassword123!",
        )

        # Try wrong password
        user = await auth_service.authenticate_user(
            s3_client, "testuser", "WrongPassword456!"
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, auth_service, s3_client):
        """Test authentication with nonexistent username."""
        user = await auth_service.authenticate_user(
            s3_client, "nonexistent", "password123"
        )

        assert user is None

    def test_create_access_token(self, auth_service):
        """Test JWT token creation."""
        data = {"sub": "testuser", "user_id": "123"}
        token = auth_service.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode token
        payload = jwt.decode(
            token, auth_service.secret_key, algorithms=[auth_service.algorithm]
        )

        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123"
        assert "exp" in payload

    def test_create_access_token_with_expiry(self, auth_service):
        """Test token creation with custom expiry."""
        from datetime import timezone

        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=15)
        token = auth_service.create_access_token(data, expires_delta)

        payload = jwt.decode(
            token, auth_service.secret_key, algorithms=[auth_service.algorithm]
        )

        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = exp_time - now

        # Should be approximately 15 minutes
        assert 14 < delta.total_seconds() / 60 < 16

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, auth_service, s3_client):
        """Test getting user by username."""
        # Create user
        created_user = await auth_service.create_user(
            s3_client,
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

        # Get by username
        user = await auth_service.get_user_by_username(s3_client, "testuser")

        assert user is not None
        assert user.id == created_user.id
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, auth_service, s3_client):
        """Test getting user by email."""
        # Create user
        created_user = await auth_service.create_user(
            s3_client,
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

        # Get by email
        user = await auth_service.get_user_by_email(s3_client, "test@example.com")

        assert user is not None
        assert user.id == created_user.id
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_authenticate(self, auth_service, s3_client):
        """Test that inactive users cannot authenticate."""
        # Create user
        user = await auth_service.create_user(
            s3_client,
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

        # Deactivate user by setting is_active to False
        user.is_active = False
        key = user.s3_key
        await s3_client.put_object(
            Bucket="test-bucket",
            Key=key,
            Body=json.dumps(user.model_dump(), default=str),
            ContentType="application/json",
        )

        # Try to authenticate
        authenticated = await auth_service.authenticate_user(
            s3_client, "testuser", "SecurePass123!"
        )

        assert authenticated is None

    def test_verify_password(self, auth_service):
        """Test password verification."""
        password = "TestPassword123!"
        hashed = auth_service.get_password_hash(password)

        assert auth_service.verify_password(password, hashed) is True
        assert auth_service.verify_password("WrongPassword", hashed) is False

    def test_password_hashing(self, auth_service):
        """Test that passwords are properly hashed."""
        password = "MySecurePassword123!"
        hashed = auth_service.get_password_hash(password)

        assert hashed != password
        assert hashed.startswith("$2b$")

        # Same password should produce different hashes (salt)
        hashed2 = auth_service.get_password_hash(password)
        assert hashed != hashed2

        # But both should verify correctly
        assert auth_service.verify_password(password, hashed) is True
        assert auth_service.verify_password(password, hashed2) is True
