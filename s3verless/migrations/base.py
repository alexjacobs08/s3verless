"""Base classes for S3verless migrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, List


@dataclass
class MigrationOperation(ABC):
    """Base class for migration operations.

    Each operation defines a forward transformation and optionally
    a reverse transformation for rollback support.
    """

    @abstractmethod
    def forward(self, data: dict) -> dict:
        """Apply the forward transformation.

        Args:
            data: The object data to transform

        Returns:
            Transformed data
        """
        pass

    def reverse(self, data: dict) -> dict:
        """Apply the reverse transformation (for rollback).

        Args:
            data: The object data to transform

        Returns:
            Transformed data

        Raises:
            NotImplementedError: If operation is not reversible
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support rollback"
        )


@dataclass
class Migration:
    """A migration that transforms data for a specific model.

    Migrations are versioned and can be applied forward or rolled back.

    Attributes:
        version: Unique version identifier (e.g., "001", "20240101_001")
        description: Human-readable description of the migration
        model_name: Name of the model this migration applies to
        operations: List of operations to apply
        reversible: Whether this migration can be rolled back
    """

    version: str
    description: str
    model_name: str
    operations: List[MigrationOperation] = field(default_factory=list)
    reversible: bool = True

    def apply(self, data: dict) -> dict:
        """Apply all operations in forward order.

        Args:
            data: The object data to transform

        Returns:
            Transformed data
        """
        result = data.copy()
        for op in self.operations:
            result = op.forward(result)
        return result

    def rollback(self, data: dict) -> dict:
        """Apply all operations in reverse order (rollback).

        Args:
            data: The object data to transform

        Returns:
            Transformed data

        Raises:
            NotImplementedError: If any operation is not reversible
        """
        if not self.reversible:
            raise NotImplementedError(
                f"Migration {self.version} is not reversible"
            )

        result = data.copy()
        for op in reversed(self.operations):
            result = op.reverse(result)
        return result


@dataclass
class MigrationRecord:
    """Record of an applied migration stored in S3."""

    version: str
    model_name: str
    description: str
    applied_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    objects_transformed: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "model_name": self.model_name,
            "description": self.description,
            "applied_at": self.applied_at.isoformat(),
            "objects_transformed": self.objects_transformed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MigrationRecord":
        """Create from dictionary."""
        return cls(
            version=data["version"],
            model_name=data["model_name"],
            description=data["description"],
            applied_at=datetime.fromisoformat(data["applied_at"]),
            objects_transformed=data.get("objects_transformed", 0),
        )
