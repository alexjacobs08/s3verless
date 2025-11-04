# Authentication & Authorization Example

Complete user authentication system with JWT tokens and protected routes.

## Features

- **User Registration**: Create new user accounts with validation
- **Login/Logout**: JWT token-based authentication
- **Password Security**: Bcrypt hashing with salt
- **Protected Routes**: Require authentication for specific endpoints
- **Token Management**: JWT token generation and validation
- **User Profile**: Access current user information

## Setup

```bash
# Install dependencies
# Using uv (recommended)
uv pip install s3verless uvicorn

# Or using pip
# pip install s3verless uvicorn

# Note: python-jose and passlib are already included with s3verless

# Start LocalStack (for local development)
docker run -d -p 4566:4566 localstack/localstack

# Set environment variables
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_BUCKET_NAME=auth-example
export SECRET_KEY=your-super-secret-key-change-in-production
export ALGORITHM=HS256
export ACCESS_TOKEN_EXPIRE_MINUTES=30

# Run the application
python main.py
```

**Note**: The app will try to connect to S3. Make sure LocalStack is running or configure real AWS credentials.

## API Endpoints

### Public Endpoints (No Auth Required)

- `POST /register` - Register a new user
- `POST /token` - Login and get access token
- `GET /` - API information
- `GET /docs` - API documentation

### Protected Endpoints (Auth Required)

- `GET /users/me` - Get current user profile
- `GET /protected` - Example protected route

## Usage Examples

### 1. Register a New User

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePassword123!",
    "full_name": "John Doe"
  }'
```

Response:
```json
{
  "id": "uuid-here",
  "username": "johndoe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00"
}
```

### 2. Login and Get Token

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=johndoe&password=SecurePassword123!"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. Access Protected Route

```bash
# Store the token
TOKEN="your-access-token-here"

# Use the token to access protected routes
curl http://localhost:8000/users/me \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "id": "uuid-here",
  "username": "johndoe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00"
}
```

### 4. Access Another Protected Route

```bash
curl http://localhost:8000/protected \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "message": "Hello johndoe! This is a protected route.",
  "user_id": "uuid-here"
}
```

## Password Requirements

Passwords must meet the following criteria:
- Minimum 8 characters long
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character (!@#$%^&*(),.?":{}|<>)

## Security Features

1. **Password Hashing**: Passwords are hashed using bcrypt with automatic salt generation
2. **JWT Tokens**: Stateless authentication with configurable expiration
3. **Token Validation**: All protected routes validate tokens automatically
4. **User Status**: Inactive users cannot authenticate
5. **Unique Constraints**: Usernames and emails must be unique

## Testing with Interactive Docs

Visit http://localhost:8000/docs for Swagger UI where you can:

1. Register a new user using the `/register` endpoint
2. Login using the `/token` endpoint (get your access token)
3. Click "Authorize" button at the top
4. Enter your token in the format: `Bearer your-token-here`
5. Access protected endpoints

## Error Handling

### Invalid Credentials
```bash
curl -X POST http://localhost:8000/token \
  -d "username=wrong&password=wrong"
```
Response: `401 Unauthorized - Incorrect username or password`

### Missing/Invalid Token
```bash
curl http://localhost:8000/users/me
```
Response: `401 Unauthorized - Not authenticated`

### Duplicate Username/Email
```bash
curl -X POST http://localhost:8000/register \
  -d '{"username": "existing", "email": "exists@example.com", "password": "Pass123!"}'
```
Response: `400 Bad Request - Username already exists`

## Integration with Your App

To add authentication to your S3verless app:

```python
from s3verless.auth.service import S3AuthService
from s3verless.fastapi.dependencies import get_s3_client

# Initialize auth service
auth_service = S3AuthService(settings)

# Add dependency for protected routes
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    s3_client = Depends(get_s3_client)
):
    # Validate token and return user
    ...

# Use in your routes
@app.get("/my-protected-route")
async def my_route(current_user = Depends(get_current_user)):
    return {"message": f"Hello {current_user.username}"}
```

## Production Considerations

1. **SECRET_KEY**: Use a strong, random secret key (not the example value!)
2. **HTTPS**: Always use HTTPS in production
3. **Token Expiry**: Adjust based on security requirements
4. **Rate Limiting**: Add rate limiting to prevent brute force attacks
5. **Password Policy**: Enforce strong password requirements
6. **Token Refresh**: Implement token refresh mechanism for long sessions
7. **Audit Logging**: Log authentication events

