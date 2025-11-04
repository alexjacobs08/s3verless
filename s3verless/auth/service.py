"""Authentication service for S3verless."""

import re
from datetime import datetime, timedelta, timezone

from aiobotocore.client import AioBaseClient
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import EmailStr

from s3verless.auth.models import S3User
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
    token generation/validation, and user management.
    """

    def __init__(
        self,
        settings: S3verlessSettings | None = None,
        secret_key: str | None = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        bucket_name: str | None = None,
    ):
        """Initialize the auth service.

        Args:
            settings: S3verlessSettings instance (preferred)
            secret_key: Secret key for JWT token signing (if settings not provided)
            algorithm: JWT algorithm to use
            access_token_expire_minutes: Token expiration time in minutes
            bucket_name: S3 bucket name (optional, defaults to settings)
        """
        if settings:
            self.secret_key = settings.secret_key
            self.algorithm = settings.algorithm
            self.access_token_expire_minutes = settings.access_token_expire_minutes
            self.bucket_name = bucket_name or settings.aws_bucket_name
        else:
            if not secret_key:
                raise ValueError("Either settings or secret_key must be provided")
            self.secret_key = secret_key
            self.algorithm = algorithm
            self.access_token_expire_minutes = access_token_expire_minutes
            self.bucket_name = bucket_name

        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.user_service = S3DataService[S3User](S3User, self.bucket_name)

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
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
            password = password_bytes.decode("utf-8", errors="ignore")
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

    def create_access_token(
        self, data: dict, expires_delta: timedelta | None = None
    ) -> str:
        """Create a JWT access token.

        Args:
            data: The data to encode in the token
            expires_delta: Optional custom expiration time

        Returns:
            The encoded JWT token
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=self.access_token_expire_minutes)
        )
        to_encode.update({"exp": expire})
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

    async def authenticate_user(
        self, s3_client: AioBaseClient, username: str, password: str
    ) -> S3User | None:
        """Authenticate a user with username and password.

        Args:
            s3_client: The S3 client to use
            username: The username to authenticate
            password: The password to verify

        Returns:
            The authenticated user if successful, None otherwise
        """
        user = await self.get_user_by_username(s3_client, username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not self.verify_password(password, user.hashed_password):
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
