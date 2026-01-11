"""Model relationships for S3verless.

This module provides relationship definitions and resolution for
linking S3-stored models together.
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Type, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from s3verless.core.base import BaseS3Model

T = TypeVar("T", bound="BaseS3Model")


class RelationType(str, Enum):
    """Types of relationships between models."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class OnDelete(str, Enum):
    """Actions to take when a related object is deleted."""

    CASCADE = "cascade"  # Delete related objects
    SET_NULL = "set_null"  # Set foreign key to null
    PROTECT = "protect"  # Prevent deletion if related objects exist
    DO_NOTHING = "do_nothing"  # Leave orphaned references


@dataclass
class Relationship:
    """Definition of a relationship between two models.

    Attributes:
        name: Name of the relationship (used for prefetch_related)
        related_model: The related model class name
        foreign_key: The field storing the foreign key
        relation_type: Type of relationship
        on_delete: Action on deletion
        back_populates: Name of reverse relationship on related model
    """

    name: str
    related_model: str  # Class name as string to avoid circular imports
    foreign_key: str
    relation_type: RelationType = RelationType.MANY_TO_ONE
    on_delete: OnDelete = OnDelete.DO_NOTHING
    back_populates: str | None = None


class RelationshipResolver:
    """Resolves and loads related objects for models.

    This class handles the loading of related objects when using
    prefetch_related() in queries.
    """

    def __init__(self, s3_client, bucket_name: str):
        """Initialize the resolver.

        Args:
            s3_client: The S3 client to use
            bucket_name: The S3 bucket name
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name

    async def resolve(
        self,
        items: list[Any],
        relationship: Relationship,
    ) -> dict[str, Any]:
        """Resolve a relationship for a list of items.

        Args:
            items: List of model instances
            relationship: The relationship to resolve

        Returns:
            Dictionary mapping item IDs to related objects
        """
        from s3verless.core.registry import get_model_by_name
        from s3verless.core.service import S3DataService

        related_model = get_model_by_name(relationship.related_model)
        if not related_model:
            return {}

        service = S3DataService(related_model, self.bucket_name)

        if relationship.relation_type == RelationType.MANY_TO_ONE:
            # Load parent objects
            return await self._resolve_many_to_one(
                items, relationship, service
            )
        elif relationship.relation_type == RelationType.ONE_TO_MANY:
            # Load child objects
            return await self._resolve_one_to_many(
                items, relationship, service
            )
        elif relationship.relation_type == RelationType.ONE_TO_ONE:
            # Load single related object
            return await self._resolve_one_to_one(
                items, relationship, service
            )
        elif relationship.relation_type == RelationType.MANY_TO_MANY:
            raise NotImplementedError(
                "MANY_TO_MANY relationships are not yet implemented. "
                "Consider using a junction model with two MANY_TO_ONE relationships."
            )

        return {}

    async def _resolve_many_to_one(
        self,
        items: list[Any],
        relationship: Relationship,
        service,
    ) -> dict[str, Any]:
        """Resolve many-to-one relationship (load parent objects)."""
        # Collect unique foreign key values
        fk_field = relationship.foreign_key
        fk_values = set()

        for item in items:
            fk_value = getattr(item, fk_field, None)
            if fk_value:
                fk_values.add(fk_value)

        # Load all related objects
        related_by_id = {}
        for fk_value in fk_values:
            if isinstance(fk_value, uuid.UUID):
                obj = await service.get(self.s3_client, fk_value)
                if obj:
                    related_by_id[str(fk_value)] = obj
            elif isinstance(fk_value, str):
                try:
                    obj = await service.get(self.s3_client, uuid.UUID(fk_value))
                    if obj:
                        related_by_id[fk_value] = obj
                except ValueError:
                    pass

        # Map item IDs to related objects
        result = {}
        for item in items:
            fk_value = getattr(item, fk_field, None)
            if fk_value:
                fk_str = str(fk_value)
                result[str(item.id)] = related_by_id.get(fk_str)

        return result

    async def _resolve_one_to_many(
        self,
        items: list[Any],
        relationship: Relationship,
        service,
    ) -> dict[str, Any]:
        """Resolve one-to-many relationship (load child objects)."""
        # Load all potential child objects
        all_children, _ = await service.list_by_prefix(
            self.s3_client, limit=10000
        )

        # Group children by foreign key value
        fk_field = relationship.foreign_key
        children_by_parent = {}

        for child in all_children:
            fk_value = getattr(child, fk_field, None)
            if fk_value:
                fk_str = str(fk_value)
                if fk_str not in children_by_parent:
                    children_by_parent[fk_str] = []
                children_by_parent[fk_str].append(child)

        # Map parent IDs to their children
        result = {}
        for item in items:
            result[str(item.id)] = children_by_parent.get(str(item.id), [])

        return result

    async def _resolve_one_to_one(
        self,
        items: list[Any],
        relationship: Relationship,
        service,
    ) -> dict[str, Any]:
        """Resolve one-to-one relationship."""
        # Same as many-to-one but expect single result
        return await self._resolve_many_to_one(items, relationship, service)


class CascadeHandler:
    """Handles cascading operations when models are deleted.

    This class manages the deletion of related objects when a model
    with cascade relationships is deleted.
    """

    def __init__(self, s3_client, bucket_name: str):
        """Initialize the cascade handler.

        Args:
            s3_client: The S3 client to use
            bucket_name: The S3 bucket name
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name

    async def handle_delete(
        self,
        model_instance: Any,
        relationships: list[Relationship],
    ) -> dict:
        """Handle cascading operations for a model being deleted.

        Args:
            model_instance: The model instance being deleted
            relationships: List of relationships to check

        Returns:
            Dictionary with counts of affected objects

        Raises:
            ValueError: If deletion is prevented by PROTECT relationship
        """
        from s3verless.core.registry import get_model_by_name
        from s3verless.core.service import S3DataService

        results = {
            "cascaded": 0,
            "set_null": 0,
            "protected": [],
        }

        for rel in relationships:
            if rel.relation_type not in (RelationType.ONE_TO_MANY, RelationType.ONE_TO_ONE):
                continue

            related_model = get_model_by_name(rel.related_model)
            if not related_model:
                continue

            service = S3DataService(related_model, self.bucket_name)

            # Find related objects
            all_related, _ = await service.list_by_prefix(
                self.s3_client, limit=10000
            )
            related_objects = [
                obj for obj in all_related
                if str(getattr(obj, rel.foreign_key, None)) == str(model_instance.id)
            ]

            if not related_objects:
                continue

            if rel.on_delete == OnDelete.PROTECT:
                results["protected"].append({
                    "relationship": rel.name,
                    "count": len(related_objects),
                })

            elif rel.on_delete == OnDelete.CASCADE:
                # Delete related objects
                for obj in related_objects:
                    await service.delete(self.s3_client, obj.id)
                    results["cascaded"] += 1

            elif rel.on_delete == OnDelete.SET_NULL:
                # Set foreign key to null
                for obj in related_objects:
                    setattr(obj, rel.foreign_key, None)
                    await service.update(self.s3_client, obj.id, obj)
                    results["set_null"] += 1

            # DO_NOTHING: leave orphaned references

        # Check if any protected relationships prevent deletion
        if results["protected"]:
            protected_info = ", ".join(
                f"{p['relationship']} ({p['count']} objects)"
                for p in results["protected"]
            )
            raise ValueError(
                f"Cannot delete: protected by relationships: {protected_info}"
            )

        return results


# Helper functions for defining relationships in models

def foreign_key(
    related_model: str,
    on_delete: OnDelete = OnDelete.DO_NOTHING,
    back_populates: str | None = None,
) -> Relationship:
    """Define a foreign key relationship (many-to-one).

    Args:
        related_model: Name of the related model class
        on_delete: Action on deletion of related object
        back_populates: Name of reverse relationship

    Returns:
        Relationship definition

    Example:
        class Post(BaseS3Model):
            author_id: uuid.UUID
            _relationships = [
                foreign_key("Author", back_populates="posts")
            ]
    """
    return Relationship(
        name="",  # Will be set from field name
        related_model=related_model,
        foreign_key="",  # Will be set from field name
        relation_type=RelationType.MANY_TO_ONE,
        on_delete=on_delete,
        back_populates=back_populates,
    )


def has_many(
    related_model: str,
    foreign_key: str,
    on_delete: OnDelete = OnDelete.DO_NOTHING,
    back_populates: str | None = None,
) -> Relationship:
    """Define a has-many relationship (one-to-many).

    Args:
        related_model: Name of the related model class
        foreign_key: Field on related model that references this model
        on_delete: Action when this model is deleted
        back_populates: Name of reverse relationship

    Returns:
        Relationship definition

    Example:
        class Author(BaseS3Model):
            name: str
            _relationships = [
                has_many("Post", "author_id", on_delete=OnDelete.CASCADE)
            ]
    """
    return Relationship(
        name="",  # Will be set based on related model
        related_model=related_model,
        foreign_key=foreign_key,
        relation_type=RelationType.ONE_TO_MANY,
        on_delete=on_delete,
        back_populates=back_populates,
    )


def has_one(
    related_model: str,
    foreign_key: str,
    on_delete: OnDelete = OnDelete.DO_NOTHING,
) -> Relationship:
    """Define a has-one relationship (one-to-one).

    Args:
        related_model: Name of the related model class
        foreign_key: Field on related model that references this model
        on_delete: Action when this model is deleted

    Returns:
        Relationship definition
    """
    return Relationship(
        name="",
        related_model=related_model,
        foreign_key=foreign_key,
        relation_type=RelationType.ONE_TO_ONE,
        on_delete=on_delete,
    )
