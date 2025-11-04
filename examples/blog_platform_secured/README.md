# Secured Blog Platform Example

This example shows how to add authentication and authorization to your S3verless application.

## Security Model

### Public Endpoints (No Authentication Required)
Anyone can access these:
- `GET /api/posts/` - List all published posts
- `GET /api/posts/{id}` - View a single post
- `GET /api/authors/` - List authors
- `POST /register` - Register a new account
- `POST /token` - Login and get access token

### Protected Endpoints (Authentication Required)
Must provide JWT token in `Authorization: Bearer <token>` header:
- `POST /api/posts/` - **Create** a new post (requires login)
- `PUT /api/posts/{id}` - **Update** a post (must be the post author)
- `DELETE /api/posts/{id}` - **Delete** a post (must be the post author)

### Authorization Rules
1. **All write operations** (create/update/delete) require authentication
2. **Ownership checks**: You can only update/delete YOUR OWN posts
3. **Read operations** are public (no login needed)

## Setup

```bash
# Install dependencies
uv pip install s3verless uvicorn

# Start LocalStack
docker run -d -p 4566:4566 localstack/localstack

# Set environment variables
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

# Run the application
python main.py
```

## Usage Workflow

### 1. Register a User

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "full_name": "John Doe"
  }'
```

This creates both a `S3User` (for authentication) and an `Author` (for blog posts).

### 2. Login and Get Token

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=johndoe&password=SecurePass123!"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. Create a Post (Protected)

```bash
TOKEN="your-token-here"

curl -X POST http://localhost:8000/api/posts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "This is my first blog post...",
    "category": "Personal",
    "tags": ["intro", "blog"],
    "status": "published"
  }'
```

**Without token**: Returns `401 Unauthorized`

### 4. View Posts (Public)

```bash
# Anyone can view published posts
curl http://localhost:8000/api/posts/
```

### 5. Update Your Own Post (Protected)

```bash
curl -X PUT http://localhost:8000/api/posts/{post_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Title",
    "status": "published"
  }'
```

**If you try to edit someone else's post**: Returns `403 Forbidden`

## Key Differences from Basic Example

### 1. **Manual Router Creation**
Instead of auto-generated CRUD for everything:
```python
app_instance = S3verless(
    auto_discover=False  # Don't auto-generate routes
)

# Manually create posts router with custom auth logic
@posts_router.post("/")
async def create_post(
    current_user: S3User = Depends(get_current_user),  # ← Requires auth
    ...
):
    # Only authenticated users can create
```

### 2. **Mixed Public/Protected Routes**
- `GET` requests are public
- `POST`, `PUT`, `DELETE` require authentication

### 3. **Author Ownership Checks**
```python
# Verify user owns the post
if authors[0].id != post.author_id:
    raise HTTPException(status_code=403, detail="Not your post")
```

### 4. **User + Author Relationship**
- `S3User` for authentication (username, password)
- `Author` for blog content (bio, avatar, posts)
- Linked by `user_id`

## Testing with Swagger UI

1. Visit http://localhost:8000/docs
2. Register a user at `/register`
3. Login at `/token` to get your access token
4. Click the "Authorize" button (🔒 icon)
5. Enter: `Bearer your-token-here`
6. Now you can access protected endpoints!

## Adding Auth to Auto-Generated Routes

If you want auto-generated CRUD with auth:

```python
from s3verless.fastapi.router_generator import generate_crud_router

# Generate router with authentication dependency
router = generate_crud_router(
    Post,
    settings,
    dependencies=[Depends(get_current_user)]  # ← All routes require auth
)
app.include_router(router)
```

This makes **all** CRUD operations require authentication.

## Production Considerations

For a production blog:
- Use strong `SECRET_KEY`
- Implement refresh tokens
- Add rate limiting
- Use HTTPS
- Add role-based permissions (admin, editor, author, reader)
- Track post revisions
- Add comment moderation
- Implement spam protection

