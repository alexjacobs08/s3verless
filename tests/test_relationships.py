"""Tests for relationships module."""

import pytest
import uuid
from typing import ClassVar

from s3verless.core.base import BaseS3Model
from s3verless.core.relationships import (
    Relationship,
    RelationType,
    OnDelete,
    foreign_key,
    has_many,
    has_one,
    RelationshipResolver,
    CascadeHandler,
)
from s3verless.core.registry import register_model, reset_registry


class RelAuthor(BaseS3Model):
    """Author model for relationship tests."""

    _plural_name: ClassVar[str] = "rel_authors"

    name: str
    email: str


class RelPost(BaseS3Model):
    """Post model for relationship tests."""

    _plural_name: ClassVar[str] = "rel_posts"

    title: str
    content: str
    author_id: uuid.UUID | None = None


class RelComment(BaseS3Model):
    """Comment model for relationship tests."""

    _plural_name: ClassVar[str] = "rel_comments"

    text: str
    post_id: uuid.UUID | None = None


class TestRelationship:
    """Tests for Relationship dataclass."""

    def test_relationship_creation(self):
        """Test creating a relationship."""
        rel = Relationship(
            name="author",
            related_model="RelAuthor",
            foreign_key="author_id",
            relation_type=RelationType.MANY_TO_ONE
        )

        assert rel.name == "author"
        assert rel.related_model == "RelAuthor"
        assert rel.foreign_key == "author_id"

    def test_relationship_default_on_delete(self):
        """Test default on_delete behavior."""
        rel = Relationship(
            name="author",
            related_model="RelAuthor",
            foreign_key="author_id",
            relation_type=RelationType.MANY_TO_ONE
        )

        assert rel.on_delete == OnDelete.DO_NOTHING


class TestRelationshipDecorators:
    """Tests for relationship decorator functions."""

    def test_foreign_key(self):
        """Test foreign_key decorator."""
        rel = foreign_key("RelAuthor", on_delete=OnDelete.CASCADE)

        assert rel.related_model == "RelAuthor"
        assert rel.relation_type == RelationType.MANY_TO_ONE
        assert rel.on_delete == OnDelete.CASCADE

    def test_has_many(self):
        """Test has_many decorator."""
        rel = has_many("RelPost", foreign_key="author_id")

        assert rel.related_model == "RelPost"
        assert rel.relation_type == RelationType.ONE_TO_MANY
        assert rel.foreign_key == "author_id"

    def test_has_one(self):
        """Test has_one decorator."""
        rel = has_one("Profile", foreign_key="user_id")

        assert rel.related_model == "Profile"
        assert rel.relation_type == RelationType.ONE_TO_ONE
        assert rel.foreign_key == "user_id"


class TestRelationType:
    """Tests for RelationType enum."""

    def test_relation_types_exist(self):
        """Test that all relation types exist."""
        assert RelationType.ONE_TO_ONE is not None
        assert RelationType.ONE_TO_MANY is not None
        assert RelationType.MANY_TO_ONE is not None
        assert RelationType.MANY_TO_MANY is not None


class TestOnDelete:
    """Tests for OnDelete enum."""

    def test_on_delete_options_exist(self):
        """Test that all on_delete options exist."""
        assert OnDelete.CASCADE is not None
        assert OnDelete.SET_NULL is not None
        assert OnDelete.PROTECT is not None
        assert OnDelete.DO_NOTHING is not None


class TestRelationshipResolver:
    """Tests for RelationshipResolver."""

    @pytest.fixture
    def mock_s3(self):
        """Create a mock S3 client."""
        from s3verless.testing.mocks import InMemoryS3
        return InMemoryS3()

    @pytest.fixture(autouse=True)
    def setup_registry(self):
        """Setup and teardown registry for each test."""
        reset_registry()
        register_model(RelAuthor)
        register_model(RelPost)
        register_model(RelComment)
        yield
        reset_registry()

    @pytest.mark.asyncio
    async def test_resolve_belongs_to(self, mock_s3):
        """Test resolving a belongs_to relationship."""
        # Create an author
        author = RelAuthor(name="John Doe", email="john@example.com")
        author_key = f"rel_authors/{author.id}.json"
        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=author_key,
            Body=author.model_dump_json().encode()
        )

        # Create a post with author_id
        post = RelPost(title="Test Post", content="Content", author_id=author.id)

        # Resolve the relationship
        resolver = RelationshipResolver(mock_s3, "test-bucket")
        rel = Relationship(
            name="author",
            related_model="RelAuthor",
            foreign_key="author_id",
            relation_type=RelationType.MANY_TO_ONE
        )

        result = await resolver.resolve([post], rel)

        assert str(post.id) in result
        assert result[str(post.id)].name == "John Doe"

    @pytest.mark.asyncio
    async def test_resolve_has_many(self, mock_s3):
        """Test resolving a has_many relationship."""
        # Create an author
        author = RelAuthor(name="Jane Doe", email="jane@example.com")

        # Create posts for the author
        post1 = RelPost(title="Post 1", content="Content 1", author_id=author.id)
        post2 = RelPost(title="Post 2", content="Content 2", author_id=author.id)

        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_posts/{post1.id}.json",
            Body=post1.model_dump_json().encode()
        )
        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_posts/{post2.id}.json",
            Body=post2.model_dump_json().encode()
        )

        # Resolve the relationship
        resolver = RelationshipResolver(mock_s3, "test-bucket")
        rel = Relationship(
            name="posts",
            related_model="RelPost",
            foreign_key="author_id",
            relation_type=RelationType.ONE_TO_MANY
        )

        result = await resolver.resolve([author], rel)

        assert str(author.id) in result
        assert len(result[str(author.id)]) == 2

    @pytest.mark.asyncio
    async def test_resolve_with_no_related(self, mock_s3):
        """Test resolving when no related objects exist."""
        author = RelAuthor(name="Lonely Author", email="lonely@example.com")

        resolver = RelationshipResolver(mock_s3, "test-bucket")
        rel = Relationship(
            name="posts",
            related_model="RelPost",
            foreign_key="author_id",
            relation_type=RelationType.ONE_TO_MANY
        )

        result = await resolver.resolve([author], rel)

        # Should have empty list for author
        assert str(author.id) in result
        assert len(result[str(author.id)]) == 0


class TestCascadeHandler:
    """Tests for CascadeHandler."""

    @pytest.fixture
    def mock_s3(self):
        """Create a mock S3 client."""
        from s3verless.testing.mocks import InMemoryS3
        return InMemoryS3()

    @pytest.fixture(autouse=True)
    def setup_registry(self):
        """Setup and teardown registry for each test."""
        reset_registry()
        register_model(RelAuthor)
        register_model(RelPost)
        register_model(RelComment)
        yield
        reset_registry()

    @pytest.mark.asyncio
    async def test_cascade_delete(self, mock_s3):
        """Test cascade delete removes related objects."""
        # Create author and posts
        author = RelAuthor(name="Author", email="author@example.com")
        post1 = RelPost(title="Post 1", content="Content", author_id=author.id)
        post2 = RelPost(title="Post 2", content="Content", author_id=author.id)

        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_authors/{author.id}.json",
            Body=author.model_dump_json().encode()
        )
        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_posts/{post1.id}.json",
            Body=post1.model_dump_json().encode()
        )
        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_posts/{post2.id}.json",
            Body=post2.model_dump_json().encode()
        )

        # Define cascade relationship
        relationships = [
            Relationship(
                name="posts",
                related_model="RelPost",
                foreign_key="author_id",
                relation_type=RelationType.ONE_TO_MANY,
                on_delete=OnDelete.CASCADE
            )
        ]

        handler = CascadeHandler(mock_s3, "test-bucket")
        result = await handler.handle_delete(author, relationships)

        assert result["cascaded"] == 2

    @pytest.mark.asyncio
    async def test_protect_prevents_delete(self, mock_s3):
        """Test PROTECT prevents deletion when related objects exist."""
        author = RelAuthor(name="Protected", email="protected@example.com")
        post = RelPost(title="Post", content="Content", author_id=author.id)

        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_posts/{post.id}.json",
            Body=post.model_dump_json().encode()
        )

        relationships = [
            Relationship(
                name="posts",
                related_model="RelPost",
                foreign_key="author_id",
                relation_type=RelationType.ONE_TO_MANY,
                on_delete=OnDelete.PROTECT
            )
        ]

        handler = CascadeHandler(mock_s3, "test-bucket")

        with pytest.raises(ValueError, match="protected"):
            await handler.handle_delete(author, relationships)

    @pytest.mark.asyncio
    async def test_set_null(self, mock_s3):
        """Test SET_NULL sets foreign key to null."""
        author = RelAuthor(name="Author", email="author@example.com")
        post = RelPost(title="Post", content="Content", author_id=author.id)

        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_posts/{post.id}.json",
            Body=post.model_dump_json().encode()
        )

        relationships = [
            Relationship(
                name="posts",
                related_model="RelPost",
                foreign_key="author_id",
                relation_type=RelationType.ONE_TO_MANY,
                on_delete=OnDelete.SET_NULL
            )
        ]

        handler = CascadeHandler(mock_s3, "test-bucket")
        result = await handler.handle_delete(author, relationships)

        assert result["set_null"] == 1

    @pytest.mark.asyncio
    async def test_do_nothing(self, mock_s3):
        """Test DO_NOTHING leaves related objects unchanged."""
        author = RelAuthor(name="Author", email="author@example.com")
        post = RelPost(title="Post", content="Content", author_id=author.id)

        await mock_s3.put_object(
            Bucket="test-bucket",
            Key=f"rel_posts/{post.id}.json",
            Body=post.model_dump_json().encode()
        )

        relationships = [
            Relationship(
                name="posts",
                related_model="RelPost",
                foreign_key="author_id",
                relation_type=RelationType.ONE_TO_MANY,
                on_delete=OnDelete.DO_NOTHING
            )
        ]

        handler = CascadeHandler(mock_s3, "test-bucket")
        result = await handler.handle_delete(author, relationships)

        assert result["cascaded"] == 0
        assert result["set_null"] == 0
