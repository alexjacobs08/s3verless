"""Authentication service for S3verless."""

import asyncio
import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from aiobotocore.client import AioBaseClient
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import EmailStr

from s3verless.auth.models import RefreshToken, S3User
from s3verless.core.exceptions import S3AuthError, S3ValidationError
from s3verless.core.service import S3DataService
from s3verless.core.settings import S3verlessSettings

# Password validation patterns
PATTERNS = {
    "uppercase": re.compile(r"[A-Z]"),
    "lowercase": re.compile(r"[a-z]"),
    "digit": re.compile(r"\d"),
    "special": re.compile(r"[!@#$%^&*(),.?\":{}|<>]"),
}


class S3AuthService:
    """Authentication service for S3verless.

    This service handles user authentication, password hashing,
    token generation/validation, and user management. It supports
    both access tokens (short-lived) and refresh tokens (long-lived).
    """

    def __init__(
        self,
        settings: S3verlessSettings | None = None,
        secret_key: str | None = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
        bucket_name: str | None = None,
    ):
        """Initialize the auth service.

        Args:
            settings: S3verlessSettings instance (preferred)
            secret_key: Secret key for JWT token signing (if settings not provided)
            algorithm: JWT algorithm to use
            access_token_expire_minutes: Access token expiration in minutes
            refresh_token_expire_days: Refresh token expiration in days
            bucket_name: S3 bucket name (optional, defaults to settings)
        """
        if settings:
            self.secret_key = settings.secret_key
            self.algorithm = settings.algorithm
            self.access_token_expire_minutes = getattr(
                settings, "access_token_expire_minutes", access_token_expire_minutes
            )
            self.refresh_token_expire_days = getattr(
                settings, "refresh_token_expire_days", refresh_token_expire_days
            )
            self.bucket_name = bucket_name or settings.aws_bucket_name
        else:
            if not secret_key:
                raise ValueError("Either settings or secret_key must be provided")
            self.secret_key = secret_key
            self.algorithm = algorithm
            self.access_token_expire_minutes = access_token_expire_minutes
            self.refresh_token_expire_days = refresh_token_expire_days
            self.bucket_name = bucket_name

        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.user_service = S3DataService[S3User](S3User, self.bucket_name)
        self.refresh_token_service = S3DataService[RefreshToken](
            RefreshToken, self.bucket_name
        )
        # Lock for token rotation to prevent race conditions
        self._token_rotation_lock = asyncio.Lock()
        # Pre-computed dummy hash for constant-time authentication
        # This prevents timing attacks by ensuring password verification
        # always takes the same amount of time regardless of user existence
        self._dummy_hash = self.pwd_context.hash("dummy_password_for_timing")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hash.

        Args:
            plain_password: The plain text password
            hashed_password: The hashed password to verify against

        Returns:
            True if the password matches, False otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: The plain text password to hash

        Returns:
            The hashed password
        """
        # Bcrypt has a 72-byte limit, so truncate if needed
        # We must truncate at a valid UTF-8 character boundary
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            # Find the last valid UTF-8 character boundary at or before byte 72
            truncated = password_bytes[:72]
            # Decode with errors='ignore' would lose data, so we find safe boundary
            # UTF-8 continuation bytes start with 10xxxxxx (0x80-0xBF)
            while truncated and (truncated[-1] & 0xC0) == 0x80:
                truncated = truncated[:-1]
            # Also check if we're at an incomplete multi-byte sequence start
            if truncated:
                last_byte = truncated[-1]
                # Check for incomplete multi-byte sequences
                if last_byte >= 0xC0:  # Start of multi-byte but incomplete
                    truncated = truncated[:-1]
            password = truncated.decode("utf-8")
        return self.pwd_context.hash(password)

    def validate_password(self, password: str) -> tuple[bool, str]:
        """Validate password strength.

        Args:
            password: The password to validate

        Returns:
            Tuple of (is_valid, message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        missing = []
        if not PATTERNS["uppercase"].search(password):
            missing.append("uppercase letter")
        if not PATTERNS["lowercase"].search(password):
            missing.append("lowercase letter")
        if not PATTERNS["digit"].search(password):
            missing.append("number")
        if not PATTERNS["special"].search(password):
            missing.append("special character")

        if missing:
            return False, f"Password must contain at least one {', '.join(missing)}"

        return True, "Password is valid"

    def _hash_token(self, token: str) -> str:
        """Hash a token for storage.

        Args:
            token: The token to hash

        Returns:
            SHA-256 hash of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def create_access_token(
        self,
        data: dict,
        expires_delta: timedelta | None = None,
        include_jti: bool = True,
    ) -> str:
        """Create a JWT access token.

        Args:
            data: The data to encode in the token
            expires_delta: Optional custom expiration time
            include_jti: Whether to include a JWT ID for blacklisting

        Returns:
            The encoded JWT token
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=self.access_token_expire_minutes)
        )

        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access",
        })

        # Add JWT ID for blacklist support
        if include_jti:
            to_encode["jti"] = str(uuid.uuid4())

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict:
        """Decode and validate a JWT token.

        Args:
            token: The JWT token to decode

        Returns:
            The decoded token data

        Raises:
            S3AuthError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            raise S3AuthError(f"Invalid token: {e}")

    async def get_user_by_username(
        self, s3_client: AioBaseClient, username: str
    ) -> S3User | None:
        """Get a user by username.

        Args:
            s3_client: The S3 client to use
            username: The username to look up

        Returns:
            The user if found, None otherwise
        """
        users, _ = await self.user_service.list_by_prefix(s3_client, limit=1000)
        return next((u for u in users if u.username == username), None)

    async def get_user_by_email(
        self, s3_client: AioBaseClient, email: EmailStr
    ) -> S3User | None:
        """Get a user by email.

        Args:
            s3_client: The S3 client to use
            email: The email to look up

        Returns:
            The user if found, None otherwise
        """
        users, _ = await self.user_service.list_by_prefix(s3_client, limit=1000)
        return next((u for u in users if u.email == email), None)

    async def get_user_by_id(
        self, s3_client: AioBaseClient, user_id: uuid.UUID
    ) -> S3User | None:
        """Get a user by ID.

        Args:
            s3_client: The S3 client to use
            user_id: The user ID to look up

        Returns:
            The user if found, None otherwise
        """
        return await self.user_service.get(s3_client, user_id)

    async def authenticate_user(
        self, s3_client: AioBaseClient, username: str, password: str
    ) -> S3User | None:
        """Authenticate a user with username and password.

        Uses constant-time comparison to prevent timing-based user enumeration.

        Args:
            s3_client: The S3 client to use
            username: The username to authenticate
            password: The password to verify

        Returns:
            The authenticated user if successful, None otherwise
        """
        user = await self.get_user_by_username(s3_client, username)

        # Always perform password verification to prevent timing attacks
        # Use a dummy hash if user doesn't exist
        if user:
            password_valid = self.verify_password(password, user.hashed_password)
        else:
            # Perform dummy verification to maintain constant time
            self.verify_password(password, self._dummy_hash)
            password_valid = False

        if not user:
            return None
        if not user.is_active:
            return None
        if not password_valid:
            return None
        return user

    async def create_user(
        self,
        s3_client: AioBaseClient,
        username: str,
        email: EmailStr,
        password: str,
        full_name: str | None = None,
    ) -> S3User:
        """Create a new user.

        Args:
            s3_client: The S3 client to use
            username: The username for the new user
            email: The email for the new user
            password: The plain text password
            full_name: Optional full name for the user

        Returns:
            The created user

        Raises:
            S3ValidationError: If username exists or password is invalid
        """
        # Check if username exists
        if await self.get_user_by_username(s3_client, username):
            raise S3ValidationError("Username already exists")

        # Check if email exists
        if await self.get_user_by_email(s3_client, email):
            raise S3ValidationError("Email already exists")

        # Validate password
        is_valid, message = self.validate_password(password)
        if not is_valid:
            raise S3ValidationError(message)

        # Create user
        user_data = {
            "username": username,
            "email": email,
            "hashed_password": self.get_password_hash(password),
            "full_name": full_name,
        }
        return await self.user_service.create(s3_client, S3User(**user_data))

    # ===== Refresh Token Methods =====

    async def create_token_pair(
        self,
        s3_client: AioBaseClient,
        user: S3User,
        device_info: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Create both access and refresh tokens.

        Args:
            s3_client: The S3 client to use
            user: The user to create tokens for
            device_info: Optional device information
            ip_address: Optional IP address
            user_agent: Optional user agent string

        Returns:
            Dictionary with access_token, refresh_token, token_type, and expires_in

        Raises:
            S3AuthError: If user is not active
        """
        # Verify user is active before issuing tokens
        if not user.is_active:
            raise S3AuthError("User account is not active")

        # Create access token (short-lived, stateless)
        access_token = self.create_access_token(
            data={"sub": user.username, "user_id": str(user.id)}
        )

        # Create refresh token (long-lived, stored in S3)
        refresh_token = secrets.token_urlsafe(32)
        refresh_token_hash = self._hash_token(refresh_token)

        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token_hash=refresh_token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.refresh_token_expire_days),
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.refresh_token_service.create(s3_client, refresh_token_obj)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
        }

    async def refresh_access_token(
        self,
        s3_client: AioBaseClient,
        refresh_token: str,
    ) -> dict:
        """Validate refresh token and issue new token pair.

        This method implements token rotation - the old refresh token
        is revoked and a new one is issued with each refresh.

        Uses a lock to prevent race conditions where two concurrent
        refresh requests could both validate the same token.

        Args:
            s3_client: The S3 client to use
            refresh_token: The refresh token to validate

        Returns:
            Dictionary with new access_token, refresh_token, etc.

        Raises:
            S3AuthError: If refresh token is invalid or expired
        """
        token_hash = self._hash_token(refresh_token)

        # Use lock to prevent race conditions in token rotation
        async with self._token_rotation_lock:
            # Find the refresh token in S3
            tokens, _ = await self.refresh_token_service.list_by_prefix(
                s3_client, limit=1000
            )

            valid_token = None
            for t in tokens:
                if t.token_hash == token_hash and not t.revoked:
                    if t.expires_at > datetime.now(timezone.utc):
                        valid_token = t
                        break

            if not valid_token:
                raise S3AuthError("Invalid or expired refresh token")

            # Revoke old refresh token FIRST (before user lookup)
            # This prevents race conditions where another request could use this token
            valid_token.revoked = True
            valid_token.revoked_at = datetime.now(timezone.utc)
            await self.refresh_token_service.update(
                s3_client, valid_token.id, valid_token
            )

        # Get the user (outside lock since token is already revoked)
        user = await self.user_service.get(s3_client, valid_token.user_id)
        if not user or not user.is_active:
            raise S3AuthError("User not found or inactive")

        # Issue new token pair
        return await self.create_token_pair(
            s3_client,
            user,
            device_info=valid_token.device_info,
            ip_address=valid_token.ip_address,
            user_agent=valid_token.user_agent,
        )

    async def revoke_refresh_token(
        self,
        s3_client: AioBaseClient,
        refresh_token: str,
    ) -> bool:
        """Revoke a specific refresh token (logout).

        Args:
            s3_client: The S3 client to use
            refresh_token: The refresh token to revoke

        Returns:
            True if token was revoked, False if not found
        """
        token_hash = self._hash_token(refresh_token)
        tokens, _ = await self.refresh_token_service.list_by_prefix(
            s3_client, limit=1000
        )

        for t in tokens:
            if t.token_hash == token_hash:
                t.revoked = True
                t.revoked_at = datetime.now(timezone.utc)
                await self.refresh_token_service.update(s3_client, t.id, t)
                return True
        return False

    async def revoke_all_user_tokens(
        self,
        s3_client: AioBaseClient,
        user_id: uuid.UUID,
    ) -> int:
        """Revoke all refresh tokens for a user (logout all devices).

        Args:
            s3_client: The S3 client to use
            user_id: The user ID to revoke tokens for

        Returns:
            Number of tokens revoked
        """
        tokens, _ = await self.refresh_token_service.list_by_prefix(
            s3_client, limit=1000
        )
        count = 0

        for t in tokens:
            if t.user_id == user_id and not t.revoked:
                t.revoked = True
                t.revoked_at = datetime.now(timezone.utc)
                await self.refresh_token_service.update(s3_client, t.id, t)
                count += 1

        return count

    async def get_user_active_sessions(
        self,
        s3_client: AioBaseClient,
        user_id: uuid.UUID,
    ) -> list[dict]:
        """Get all active sessions for a user.

        Args:
            s3_client: The S3 client to use
            user_id: The user ID to get sessions for

        Returns:
            List of session information dictionaries
        """
        tokens, _ = await self.refresh_token_service.list_by_prefix(
            s3_client, limit=1000
        )
        now = datetime.now(timezone.utc)

        sessions = []
        for t in tokens:
            if t.user_id == user_id and not t.revoked and t.expires_at > now:
                sessions.append({
                    "id": str(t.id),
                    "device_info": t.device_info,
                    "ip_address": t.ip_address,
                    "user_agent": t.user_agent,
                    "created_at": t.created_at.isoformat(),
                    "expires_at": t.expires_at.isoformat(),
                })

        return sessions

    async def cleanup_expired_tokens(
        self,
        s3_client: AioBaseClient,
    ) -> int:
        """Clean up expired refresh tokens from S3.

        This method should be called periodically to remove expired tokens.

        Args:
            s3_client: The S3 client to use

        Returns:
            Number of tokens deleted
        """
        tokens, _ = await self.refresh_token_service.list_by_prefix(
            s3_client, limit=1000
        )
        now = datetime.now(timezone.utc)
        count = 0

        for t in tokens:
            if t.expires_at < now or t.revoked:
                await self.refresh_token_service.delete(s3_client, t.id)
                count += 1

        return count
