"""FastAPI authentication integration for S3verless."""

from typing import Annotated

from aiobotocore.client import AioBaseClient
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from s3verless.auth.models import S3User
from s3verless.auth.service import S3AuthService
from s3verless.core.exceptions import S3AuthError
from s3verless.fastapi.dependencies import get_auth_service, get_s3_client


class S3OAuth2PasswordBearer(OAuth2PasswordBearer):
    """OAuth2 password bearer scheme for S3verless."""

    def __init__(self, tokenUrl: str = "/auth/token"):
        """Initialize the OAuth2 scheme.

        Args:
            tokenUrl: The URL to get the token from
        """
        super().__init__(tokenUrl=tokenUrl)


oauth2_scheme = S3OAuth2PasswordBearer()


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    auth_service: Annotated[S3AuthService, Depends(get_auth_service)],
    s3_client: Annotated[AioBaseClient, Depends(get_s3_client)],
) -> S3User:
    """Get the current authenticated user.

    Args:
        token: The JWT token from the request
        auth_service: The auth service instance
        s3_client: The S3 client instance

    Returns:
        The authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = auth_service.decode_token(token)
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except S3AuthError:
        raise credentials_exception

    user = await auth_service.get_user_by_username(s3_client, username)
    if user is None:
        raise credentials_exception

    # Store user in request state for ownership checks
    request.state.current_user = user

    return user


async def get_current_active_user(
    current_user: Annotated[S3User, Depends(get_current_user)],
) -> S3User:
    """Get the current active user.

    Args:
        current_user: The current authenticated user

    Returns:
        The active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
