"""
Authentication & Authorization Example using S3verless

This example demonstrates:
- User registration and login
- JWT token authentication
- Protected routes
- Role-based access control
"""

from datetime import timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from s3verless import create_s3verless_app
from s3verless.auth.service import S3AuthService
from s3verless.core.settings import S3verlessSettings
from s3verless.fastapi.dependencies import get_s3_client


# Pydantic models for requests/responses
class UserCreate(BaseModel):
    """User registration request."""

    username: str
    email: EmailStr
    password: str
    full_name: str | None = None


class UserResponse(BaseModel):
    """User response (without password)."""

    id: str
    username: str
    email: str
    full_name: str | None
    is_active: bool
    created_at: str


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """JWT token payload."""

    username: str | None = None


# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Create the FastAPI app with sensible defaults
settings = S3verlessSettings(
    aws_bucket_name="auth-example-bucket",
    secret_key="dev-secret-key-change-in-production",
    access_token_expire_minutes=30,
)
app = create_s3verless_app(
    settings=settings,
    title="Auth Example API",
    description="User authentication and authorization example",
    version="1.0.0",
    enable_admin=True,
)

# Initialize auth service
auth_service = S3AuthService(settings)


async def get_current_user(
    token: str = Depends(oauth2_scheme), s3_client=Depends(get_s3_client)
):
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode the JWT token
        payload = auth_service.decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    # Get user from database
    user = await auth_service.get_user_by_username(s3_client, username)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user=Depends(get_current_user)):
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, s3_client=Depends(get_s3_client)):
    """Register a new user."""
    try:
        user = await auth_service.create_user(
            s3_client=s3_client,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
        )
        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), s3_client=Depends(get_s3_client)
):
    """Login and get JWT token."""
    user = await auth_service.authenticate_user(
        s3_client=s3_client, username=form_data.username, password=form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return Token(access_token=access_token, token_type="bearer")


@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user=Depends(get_current_active_user)):
    """Get current user profile."""
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )


@app.get("/protected")
async def protected_route(current_user=Depends(get_current_active_user)):
    """Example of a protected route that requires authentication."""
    return {
        "message": f"Hello {current_user.username}! This is a protected route.",
        "user_id": str(current_user.id),
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Auth Example API",
        "endpoints": {
            "register": "/register",
            "login": "/token",
            "profile": "/users/me",
            "protected": "/protected",
            "docs": "/docs",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
