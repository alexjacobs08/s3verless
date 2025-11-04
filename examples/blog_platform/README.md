# Blog Platform Example

A full-featured blogging platform demonstrating S3verless's **automatic ownership** and **admin role** features.

## 🎯 What This Example Shows

### Automatic Security Features
- **Ownership Protection**: Users can only edit/delete their own posts and comments
- **Admin Bypass**: Admin users can modify any resource (moderation, management)
- **Auto-set Owner**: The `user_id` field is automatically set to the current user on creation
- **Mixed Access Levels**: Categories are public, posts/comments are owned

### Key Features
- User registration and JWT authentication
- Multi-model blog system (Posts, Comments, Categories)
- Post status workflow (Draft → Published → Archived)
- Nested comments support
- Category organization
- Search and filtering
- Admin interface for content management

## 🔐 Security Model

### How Ownership Works

Simply set these flags on your model:

```python
class Post(BaseS3Model):
    _require_ownership = True  # ← Enables ownership checks
    _owner_field = "user_id"   # ← Field containing owner ID
    
    user_id: str  # This gets auto-set to current user
    title: str
```

**What happens automatically:**
- ✅ `POST /api/posts/` - Requires login, auto-sets `user_id` to current user
- ✅ `PUT /api/posts/{id}` - Only the owner (or admin) can update
- ✅ `DELETE /api/posts/{id}` - Only the owner (or admin) can delete
- ✅ `GET /api/posts/` - Public (anyone can read)

### Resource Access Control

| Model | Security | Who Can Modify |
|-------|----------|---------------|
| **Post** | Ownership required | Owner or Admin |
| **Comment** | Ownership required | Owner or Admin |
| **Category** | Public | Anyone |

### Admin Privileges

Users with `is_admin=True` can:
- ✅ Modify ANY post (even if they don't own it)
- ✅ Delete ANY comment (moderation)
- ✅ Full access to all owned resources
- ✅ Bypass all ownership checks automatically

## 🚀 Setup

### Prerequisites

- Python 3.9+
- Docker (for LocalStack)
- uv or pip

### Installation

```bash
# Install S3verless
uv pip install s3verless uvicorn

# Start LocalStack (local S3 emulation)
docker run -d -p 4566:4566 localstack/localstack

# Set environment variables
export AWS_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

# Run the blog platform
cd examples/blog_platform
python main.py
```

The app will start on http://localhost:8000

### 🎁 Default Admin Account

The app automatically creates a default admin account on startup:
- **Username**: `admin`
- **Password**: `Admin123!`
- **Email**: `admin@example.com`
- **Admin**: ✅ Yes

You can immediately login to the admin interface at http://localhost:8000/admin with these credentials!

**⚠️ Production Warning**: Disable this in production by setting:
```bash
export CREATE_DEFAULT_ADMIN=false
```

Or change the defaults:
```bash
export DEFAULT_ADMIN_USERNAME=myadmin
export DEFAULT_ADMIN_PASSWORD=SuperSecure123!
export DEFAULT_ADMIN_EMAIL=admin@mysite.com
```

## 📖 Usage Guide

### Quick Start with Default Admin

**The fastest way to get started**:

1. Start the app (it creates admin automatically)
2. Visit http://localhost:8000/admin
3. Login with: `admin` / `Admin123!`
4. Start managing content!

### 1. Using the Default Admin

The app creates a default admin on startup. You can use it immediately:

**Admin Credentials**:
- Username: `admin`
- Password: `Admin123!`

No registration needed - just login and go!

### 2. Register Additional Users

```bash
# Register a regular user (author)
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "full_name": "John Doe",
    "is_admin": false
  }'

# Register another admin (if needed)
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "editor",
    "email": "editor@example.com",
    "password": "EditorPass123!",
    "full_name": "Editor User",
    "is_admin": true
  }'
```

### 3. Login and Get Token

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=john&password=SecurePass123!"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Save the token for subsequent requests:
```bash
export TOKEN="your-access-token-here"
```

### 4. Create a Post (Protected)

```bash
curl -X POST http://localhost:8000/api/posts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "author_name": "John Doe",
    "title": "My First Post",
    "slug": "my-first-post",
    "content": "This is my first blog post using S3verless!",
    "excerpt": "Getting started with S3verless",
    "category": "Tutorial",
    "tags": ["intro", "tutorial"],
    "status": "draft"
  }'
```

**Note**: The `user_id` field is **automatically set** to your user ID from the token!

### 5. List Posts (Public)

```bash
# Anyone can view posts (no auth required)
curl http://localhost:8000/api/posts/
```

### 6. Update Your Own Post

```bash
# Get the post ID from the create response
POST_ID="your-post-id-here"

curl -X PUT http://localhost:8000/api/posts/$POST_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Title",
    "status": "published"
  }'
```

**✅ Works**: You own this post  
**❌ Fails with 403**: If you try to edit someone else's post

### 7. Admin Moderation

```bash
# Login as the default admin
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=Admin123!"

export ADMIN_TOKEN="admin-token-here"

# Admin can modify ANY post (even if they don't own it)
curl -X PUT http://localhost:8000/api/posts/$POST_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "archived"
  }'
```

**Result**: ✅ Works! Admin bypass kicks in.

### 8. Create Categories (Public)

Categories don't have ownership - anyone can create them:

```bash
curl -X POST http://localhost:8000/api/categories/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Technology",
    "slug": "technology",
    "description": "Tech articles and tutorials"
  }'
```

**No authentication required!**

### 9. Add Comments (Protected)

```bash
curl -X POST http://localhost:8000/api/comments/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "John Doe",
    "post_id": "post-id-here",
    "post_title": "My First Post",
    "content": "Great post!",
    "is_approved": false
  }'
```

## 🎨 Admin Interface

Visit http://localhost:8000/admin to:

- View all posts, comments, and categories
- Create new content through forms
- Edit existing items
- Delete content
- See smart forms with proper field types

**Note**: The admin UI works for viewing all models, but editing owned resources (posts/comments) still requires proper authentication through the API.

## 🧪 Testing with Swagger UI

1. Visit http://localhost:8000/docs
2. Register a regular user at `/register`
3. Register an admin user at `/register` (set `is_admin: true`)
4. Login at `/token` to get your access token
5. Click the "Authorize" 🔒 button at the top
6. Enter: `Bearer your-token-here`
7. Now test the protected endpoints!

### Try These Scenarios:

**Scenario 1: Regular User**
- ✅ Create your own post
- ✅ Edit your own post
- ❌ Try to edit someone else's post (403 Forbidden)
- ❌ Try to delete someone else's post (403 Forbidden)

**Scenario 2: Admin User**
- ✅ Create your own post
- ✅ Edit someone else's post (admin bypass!)
- ✅ Delete any post (moderation power)
- ✅ Approve/reject any comment

## 🏗️ Architecture Highlights

### Automatic Ownership
The framework automatically:
1. Extracts `user_id` from JWT token
2. Sets `user_id` field on create
3. Checks `user_id` matches on update/delete
4. Allows admins to bypass checks

### Three Access Levels in One App

```python
# Level 1: Public
class Category(BaseS3Model):
    name: str  # Anyone can CRUD

# Level 2: Auth Required (no ownership)
class SiteSettings(BaseS3Model):
    _require_auth = True  # Any logged-in user

# Level 3: Ownership Required
class Post(BaseS3Model):
    _require_ownership = True  # Only owner or admin
    user_id: str
```

## 🔑 Key Concepts

### Owner Field
The field specified in `_owner_field` (default: `"user_id"`) must:
- Be a string field in your model
- Store the user's ID (UUID as string)
- Be automatically set on creation (you don't need to provide it)

### Admin Bypass
When a user has `is_admin=True`:
- All ownership checks are skipped
- They can access any resource
- Perfect for moderation and management

### Public vs Protected
- **GET requests** are typically public (anyone can read)
- **POST/PUT/DELETE** are protected when `_require_ownership=True`
- You control this per-model

## 📝 Best Practices

1. **Always use ownership for user content**: Posts, comments, profiles, etc.
2. **Make admin users carefully**: They have god-mode access
3. **Use categories/tags as public**: No ownership needed for taxonomies
4. **Denormalize author data**: Store `author_name` to avoid joins
5. **Use status workflows**: Draft → Published → Archived
6. **Moderate comments**: Use `is_approved` field with admin reviews

## 🚧 Production Considerations

For a production blog, you should:
- [ ] Use a strong `SECRET_KEY` (not the default)
- [ ] Implement token refresh for better security
- [ ] Add rate limiting to prevent abuse
- [ ] Use HTTPS (always!)
- [ ] Add email verification for new users
- [ ] Implement forgot password flow
- [ ] Add role management (admin creation should be restricted)
- [ ] Add audit logging
- [ ] Add image upload with presigned URLs
- [ ] Implement pagination for comments
- [ ] Add full-text search

## 💡 Customization Ideas

- Add a `Subscriber` model for email lists
- Add `Featured` posts with special flag
- Add view tracking and analytics
- Add rich text editor integration
- Add social sharing metadata
- Add RSS feed generation
- Add comment threading (nested comments)
- Add like/reaction system

## 🆘 Troubleshooting

**"Error loading data" in admin**:
- Make sure LocalStack is running: `docker ps | grep localstack`
- Or set proper AWS credentials

**401 Unauthorized**:
- Check your token is valid and not expired
- Make sure you included `Authorization: Bearer <token>` header

**403 Forbidden when editing**:
- You're trying to edit someone else's content
- Login as admin to bypass, or edit only your own posts

**422 Validation Error**:
- Check required fields in the schema
- Use Swagger UI to see what fields are needed

## 📚 Learn More

- See `examples/auth_example/` for authentication basics
- See `examples/todo_app/` for a simpler ownership-free example
- Check the main README for full S3verless documentation

---

**Built with ❤️ using S3verless's automatic ownership and admin features**
