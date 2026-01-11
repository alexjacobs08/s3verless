# Authentication Guide

Complete authentication with JWT tokens, refresh tokens, rate limiting, and authorization.

## Setup

### Configure Settings

```python
from s3verless.core.settings import S3verlessSettings

settings = S3verlessSettings(
    aws_bucket_name="my-bucket",
    secret_key="your-super-secret-key-min-32-chars",
    algorithm="HS256",
    access_token_expire_minutes=30,
    refresh_token_expire_days=7,
)
```

### Initialize Auth Service

```python
from s3verless.auth.service import S3AuthService

auth = S3AuthService(settings)
```

## User Management

### Create User

```python
user = await auth.create_user(
    s3_client,
    username="john",
    email="john@example.com",
    password="SecurePass123!",
    full_name="John Doe",
)
```

### Password Requirements

Default requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

### Find Users

```python
# By username
user = await auth.get_user_by_username(s3_client, "john")

# By email
user = await auth.get_user_by_email(s3_client, "john@example.com")

# By ID
user = await auth.get_user_by_id(s3_client, user_id)
```

## Authentication

### Login

```python
user = await auth.authenticate_user(s3_client, "john", "SecurePass123!")
if user:
    tokens = await auth.create_token_pair(
        s3_client,
        user,
        device_info="Web Browser",
        ip_address=request.client.host,
    )
    # Returns: {access_token, refresh_token, token_type, expires_in}
```

### Refresh Tokens

```python
new_tokens = await auth.refresh_access_token(s3_client, refresh_token)
```

### Logout

```python
# Revoke single token
await auth.revoke_refresh_token(s3_client, refresh_token)

# Revoke all user tokens (logout everywhere)
await auth.revoke_all_user_tokens(s3_client, user.id)
```

## FastAPI Integration

### Dependencies

```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    s3_client = Depends(get_s3_client),
    auth: S3AuthService = Depends(get_auth_service),
):
    try:
        payload = auth.decode_token(token)
        user = await auth.get_user_by_username(s3_client, payload["sub"])
        if not user or not user.is_active:
            raise HTTPException(401, "Invalid credentials")
        return user
    except Exception:
        raise HTTPException(401, "Invalid credentials")
```

### Protected Routes

```python
@app.get("/me")
async def get_profile(user: S3User = Depends(get_current_user)):
    return user

@app.put("/me")
async def update_profile(
    data: UpdateProfile,
    user: S3User = Depends(get_current_user),
    s3_client = Depends(get_s3_client),
):
    # Update user...
    pass
```

### Admin-Only Routes

```python
async def require_admin(user: S3User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user

@app.get("/admin/users")
async def list_users(admin: S3User = Depends(require_admin)):
    # Admin-only logic...
    pass
```

## Rate Limiting

### Setup

```python
from s3verless.auth.rate_limit import RateLimiter, RateLimit

limiter = RateLimiter(
    limits={
        "login": RateLimit(max_requests=5, window_seconds=60),
        "api": RateLimit(max_requests=100, window_seconds=60),
    },
    trusted_proxies=["10.0.0.1"],  # Load balancer IPs
    trust_x_forwarded_for=True,
)
```

### Apply to Routes

```python
@app.post("/auth/login")
async def login(request: Request, credentials: LoginRequest):
    is_limited, info = await limiter.is_rate_limited(request, "login")
    if is_limited:
        raise HTTPException(
            429,
            "Too many requests",
            headers=limiter.get_rate_limit_headers(info),
        )
    # Login logic...
```

### Middleware

```python
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    is_limited, info = await limiter.is_rate_limited(request, "api")
    if is_limited:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers=limiter.get_rate_limit_headers(info),
        )
    response = await call_next(request)
    return response
```

## Token Blacklisting

For immediate token revocation:

```python
from s3verless.auth.blacklist import TokenBlacklist

blacklist = TokenBlacklist(bucket_name)

# Add to blacklist
await blacklist.add(s3_client, token_jti, expires_at)

# Check in authentication
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = auth.decode_token(token)
    if await blacklist.is_blacklisted(s3_client, payload.get("jti")):
        raise HTTPException(401, "Token revoked")
    # Continue authentication...
```

## Session Management

### View Active Sessions

```python
sessions = await auth.get_user_active_sessions(s3_client, user.id)
# Returns: [{id, device_info, ip_address, created_at, expires_at}, ...]
```

### Cleanup Expired Tokens

Run periodically:

```python
deleted_count = await auth.cleanup_expired_tokens(s3_client)
```

## Complete Auth Router Example

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register(
    username: str,
    email: str,
    password: str,
    s3_client = Depends(get_s3_client),
    auth: S3AuthService = Depends(get_auth_service),
):
    try:
        user = await auth.create_user(s3_client, username, email, password)
        return {"message": "User created", "user_id": str(user.id)}
    except S3ValidationError as e:
        raise HTTPException(400, str(e))

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    s3_client = Depends(get_s3_client),
    auth: S3AuthService = Depends(get_auth_service),
):
    user = await auth.authenticate_user(
        s3_client, form_data.username, form_data.password
    )
    if not user:
        raise HTTPException(401, "Invalid credentials")

    return await auth.create_token_pair(s3_client, user)

@router.post("/refresh")
async def refresh(
    refresh_token: str,
    s3_client = Depends(get_s3_client),
    auth: S3AuthService = Depends(get_auth_service),
):
    try:
        return await auth.refresh_access_token(s3_client, refresh_token)
    except S3AuthError:
        raise HTTPException(401, "Invalid refresh token")

@router.post("/logout")
async def logout(
    refresh_token: str,
    s3_client = Depends(get_s3_client),
    auth: S3AuthService = Depends(get_auth_service),
):
    await auth.revoke_refresh_token(s3_client, refresh_token)
    return {"message": "Logged out"}
```

## Security Best Practices

1. **Use strong secret keys** - At least 32 characters, randomly generated
2. **Short access token expiry** - 15-30 minutes
3. **Rotate refresh tokens** - New refresh token on each use
4. **Rate limit auth endpoints** - Prevent brute force
5. **Use HTTPS** - Always in production
6. **Validate passwords** - Enforce complexity requirements
7. **Clean up tokens** - Run periodic cleanup jobs
