# Relationships Guide

Define and work with relationships between S3-stored models.

## Relationship Types

S3verless supports:
- **Many-to-One** - Child references parent via foreign key
- **One-to-Many** - Parent has many children
- **One-to-One** - Single related object

## Defining Relationships

### Foreign Key (Many-to-One)

A post belongs to an author:

```python
from uuid import UUID
from s3verless.core.base import BaseS3Model
from s3verless.core.relationships import foreign_key, OnDelete

class Author(BaseS3Model):
    _plural_name = "authors"
    name: str
    email: str

class Post(BaseS3Model):
    _plural_name = "posts"
    title: str
    content: str
    author_id: UUID  # Foreign key field

    _relationships = [
        foreign_key("Author", on_delete=OnDelete.CASCADE)
    ]
```

### Has Many (One-to-Many)

An author has many posts:

```python
from s3verless.core.relationships import has_many, OnDelete

class Author(BaseS3Model):
    _plural_name = "authors"
    name: str

    _relationships = [
        has_many("Post", foreign_key="author_id", on_delete=OnDelete.CASCADE)
    ]
```

### Has One (One-to-One)

A user has one profile:

```python
from s3verless.core.relationships import has_one

class User(BaseS3Model):
    _plural_name = "users"
    username: str

    _relationships = [
        has_one("Profile", foreign_key="user_id")
    ]

class Profile(BaseS3Model):
    _plural_name = "profiles"
    user_id: UUID
    bio: str
```

## On Delete Behavior

Control what happens when a related object is deleted:

```python
from s3verless.core.relationships import OnDelete

# CASCADE - Delete related objects
has_many("Post", "author_id", on_delete=OnDelete.CASCADE)

# SET_NULL - Set foreign key to null
has_many("Post", "author_id", on_delete=OnDelete.SET_NULL)

# PROTECT - Prevent deletion if related objects exist
has_many("Post", "author_id", on_delete=OnDelete.PROTECT)

# DO_NOTHING - Leave orphaned references (default)
has_many("Post", "author_id", on_delete=OnDelete.DO_NOTHING)
```

## Loading Related Objects

### Manual Loading

```python
from s3verless.core.service import S3DataService

# Get post with author
post_service = S3DataService(Post, bucket)
author_service = S3DataService(Author, bucket)

post = await post_service.get(s3_client, post_id)
author = await author_service.get(s3_client, post.author_id)
```

### Relationship Resolver

```python
from s3verless.core.relationships import RelationshipResolver

resolver = RelationshipResolver(s3_client, bucket)

# Resolve many-to-one (get authors for posts)
posts = await Query(Post, s3_client, bucket).all()
relationship = Post._relationships[0]  # author relationship
author_map = await resolver.resolve(posts, relationship)
# {post_id: author_object, ...}
```

## Cascade Handler

Handle cascading deletes:

```python
from s3verless.core.relationships import CascadeHandler

handler = CascadeHandler(s3_client, bucket)

# Before deleting an author
author = await author_service.get(s3_client, author_id)
try:
    results = await handler.handle_delete(author, Author._relationships)
    # results: {cascaded: n, set_null: n, protected: []}
    await author_service.delete(s3_client, author_id)
except ValueError as e:
    # Deletion blocked by PROTECT relationship
    print(f"Cannot delete: {e}")
```

## Example: Blog with Comments

```python
from uuid import UUID
from s3verless.core.base import BaseS3Model
from s3verless.core.relationships import has_many, foreign_key, OnDelete

class Author(BaseS3Model):
    _plural_name = "authors"
    name: str
    bio: str | None = None

    _relationships = [
        has_many("Post", "author_id", on_delete=OnDelete.CASCADE)
    ]

class Post(BaseS3Model):
    _plural_name = "posts"
    title: str
    content: str
    author_id: UUID
    published: bool = False

    _relationships = [
        foreign_key("Author"),
        has_many("Comment", "post_id", on_delete=OnDelete.CASCADE)
    ]

class Comment(BaseS3Model):
    _plural_name = "comments"
    content: str
    post_id: UUID
    commenter_name: str

    _relationships = [
        foreign_key("Post")
    ]
```

### Usage

```python
# Create author and post
author = await author_service.create(s3_client, Author(name="Jane"))
post = await post_service.create(s3_client, Post(
    title="Hello World",
    content="My first post",
    author_id=author.id,
))

# Add comments
comment = await comment_service.create(s3_client, Comment(
    content="Great post!",
    post_id=post.id,
    commenter_name="Reader",
))

# Delete author cascades to posts and comments
handler = CascadeHandler(s3_client, bucket)
await handler.handle_delete(author, Author._relationships)
await author_service.delete(s3_client, author.id)
# Posts and comments are now deleted
```

## Best Practices

1. **Define both sides** - Add relationships on both models for clarity
2. **Use CASCADE carefully** - Understand what will be deleted
3. **Consider PROTECT** - For critical data that shouldn't be orphaned
4. **Load efficiently** - Use resolver for batch loading
5. **Clean up orphans** - Run periodic cleanup for DO_NOTHING relationships
