"""Tests for migrations module."""

import pytest
from typing import ClassVar

from s3verless.core.base import BaseS3Model
from s3verless.migrations.base import Migration, MigrationRecord
from s3verless.migrations.operations import (
    AddField,
    RemoveField,
    RenameField,
    TransformField,
)
from s3verless.migrations.runner import MigrationRunner


class MigrationTestModel(BaseS3Model):
    """Test model for migration tests."""

    _plural_name: ClassVar[str] = "migration_test_models"

    name: str
    email: str | None = None
    status: str = "active"


class TestMigrationOperations:
    """Tests for migration operations."""

    def test_add_field(self):
        """Test AddField operation."""
        op = AddField(field_name="new_field", default="default")

        data = {"name": "test"}
        result = op.forward(data)

        assert result["new_field"] == "default"
        assert result["name"] == "test"

    def test_add_field_reverse(self):
        """Test AddField reverse operation."""
        op = AddField(field_name="new_field", default="default")

        data = {"name": "test", "new_field": "value"}
        result = op.reverse(data)

        assert "new_field" not in result
        assert result["name"] == "test"

    def test_add_field_existing_field(self):
        """Test AddField doesn't overwrite existing field."""
        op = AddField(field_name="existing", default="default")

        data = {"existing": "original"}
        result = op.forward(data)

        assert result["existing"] == "original"

    def test_remove_field(self):
        """Test RemoveField operation."""
        op = RemoveField(field_name="old_field")

        data = {"name": "test", "old_field": "value"}
        result = op.forward(data)

        assert "old_field" not in result
        assert result["name"] == "test"

    def test_remove_field_not_present(self):
        """Test RemoveField when field doesn't exist."""
        op = RemoveField(field_name="nonexistent")

        data = {"name": "test"}
        result = op.forward(data)

        assert result == {"name": "test"}

    def test_rename_field(self):
        """Test RenameField operation."""
        op = RenameField(old_name="old_name", new_name="new_name")

        data = {"old_name": "value", "other": "data"}
        result = op.forward(data)

        assert "old_name" not in result
        assert result["new_name"] == "value"
        assert result["other"] == "data"

    def test_rename_field_reverse(self):
        """Test RenameField reverse operation."""
        op = RenameField(old_name="old_name", new_name="new_name")

        data = {"new_name": "value"}
        result = op.reverse(data)

        assert "new_name" not in result
        assert result["old_name"] == "value"

    def test_rename_field_not_present(self):
        """Test RenameField when old field doesn't exist."""
        op = RenameField(old_name="nonexistent", new_name="new_name")

        data = {"other": "data"}
        result = op.forward(data)

        assert "new_name" not in result
        assert result == {"other": "data"}

    def test_transform_field(self):
        """Test TransformField operation."""
        op = TransformField(
            field_name="status",
            forward_func=lambda x: x.upper()
        )

        data = {"status": "active"}
        result = op.forward(data)

        assert result["status"] == "ACTIVE"

    def test_transform_field_with_reverse(self):
        """Test TransformField with reverse function."""
        op = TransformField(
            field_name="status",
            forward_func=lambda x: x.upper(),
            reverse_func=lambda x: x.lower()
        )

        data = {"status": "ACTIVE"}
        result = op.reverse(data)

        assert result["status"] == "active"

    def test_transform_field_missing_field(self):
        """Test TransformField when field is missing."""
        op = TransformField(
            field_name="missing",
            forward_func=lambda x: x.upper()
        )

        data = {"other": "value"}
        result = op.forward(data)

        # Should not add the field
        assert "missing" not in result


class TestMigration:
    """Tests for Migration class."""

    def test_migration_creation(self):
        """Test creating a migration."""
        migration = Migration(
            version="001",
            description="Test migration",
            model_name="TestModel",
            operations=[
                AddField("new_field", default="default"),
            ]
        )

        assert migration.version == "001"
        assert migration.description == "Test migration"
        assert len(migration.operations) == 1

    def test_migration_apply(self):
        """Test applying a migration."""
        migration = Migration(
            version="001",
            description="Add status field",
            model_name="TestModel",
            operations=[
                AddField("status", default="pending"),
            ]
        )

        data = {"name": "test"}
        result = migration.apply(data)

        assert result["status"] == "pending"

    def test_migration_rollback(self):
        """Test rolling back a migration."""
        migration = Migration(
            version="001",
            description="Add status field",
            model_name="TestModel",
            operations=[
                AddField("status", default="pending"),
            ],
            reversible=True
        )

        data = {"name": "test", "status": "pending"}
        result = migration.rollback(data)

        assert "status" not in result

    def test_migration_multiple_operations(self):
        """Test migration with multiple operations."""
        migration = Migration(
            version="001",
            description="Multiple changes",
            model_name="TestModel",
            operations=[
                AddField("new_field", default="default"),
                RenameField("old_name", "new_name"),
                RemoveField("deprecated"),
            ]
        )

        data = {"old_name": "value", "deprecated": "old"}
        result = migration.apply(data)

        assert result["new_field"] == "default"
        assert result["new_name"] == "value"
        assert "old_name" not in result
        assert "deprecated" not in result


class TestMigrationRecord:
    """Tests for MigrationRecord."""

    def test_record_creation(self):
        """Test creating a migration record."""
        record = MigrationRecord(
            version="001",
            model_name="TestModel",
            description="Test migration",
            objects_transformed=100
        )

        assert record.version == "001"
        assert record.objects_transformed == 100
        assert record.applied_at is not None

    def test_record_to_dict(self):
        """Test converting record to dict."""
        record = MigrationRecord(
            version="001",
            model_name="TestModel",
            description="Test migration",
            objects_transformed=50
        )

        data = record.to_dict()

        assert data["version"] == "001"
        assert data["model_name"] == "TestModel"
        assert "applied_at" in data

    def test_record_from_dict(self):
        """Test creating record from dict."""
        data = {
            "version": "002",
            "model_name": "User",
            "description": "Add email",
            "objects_transformed": 200,
            "applied_at": "2025-01-01T00:00:00+00:00"
        }

        record = MigrationRecord.from_dict(data)

        assert record.version == "002"
        assert record.model_name == "User"


class TestMigrationRunner:
    """Tests for MigrationRunner."""

    @pytest.fixture
    def mock_s3(self):
        """Create a mock S3 client."""
        from s3verless.testing.mocks import InMemoryS3
        return InMemoryS3()

    @pytest.fixture
    def runner(self, mock_s3):
        """Create a migration runner."""
        return MigrationRunner(
            s3_client=mock_s3,
            bucket_name="test-bucket",
            migrations_dir=None
        )

    @pytest.mark.asyncio
    async def test_get_applied_migrations_empty(self, runner):
        """Test getting applied migrations when none exist."""
        applied = await runner.get_applied_migrations()
        assert applied == []

    @pytest.mark.asyncio
    async def test_register_migration(self, runner):
        """Test registering a migration."""
        migration = Migration(
            version="001",
            description="Test",
            model_name="TestModel",
            operations=[]
        )

        runner.register(migration)

        pending = runner.get_pending_migrations()
        assert len(pending) == 1
        assert pending[0].version == "001"

    @pytest.mark.asyncio
    async def test_run_pending_no_migrations(self, runner):
        """Test running when no migrations registered."""
        results = await runner.run_pending()
        assert results == []

    @pytest.mark.asyncio
    async def test_run_pending_skips_unknown_model(self, runner, mock_s3):
        """Test that migrations for unknown models are skipped."""
        migration = Migration(
            version="001",
            description="Test",
            model_name="UnknownModel",
            operations=[AddField("test", default="value")]
        )
        runner.register(migration)

        results = await runner.run_pending()

        assert len(results) == 1
        assert results[0]["status"] == "skipped"
        assert "not found" in results[0]["reason"]

    @pytest.mark.asyncio
    async def test_migrations_sorted_by_version(self, runner):
        """Test that migrations are sorted by version."""
        runner.register(Migration("003", "Third", "TestModel", []))
        runner.register(Migration("001", "First", "TestModel", []))
        runner.register(Migration("002", "Second", "TestModel", []))

        pending = runner.get_pending_migrations()

        assert pending[0].version == "001"
        assert pending[1].version == "002"
        assert pending[2].version == "003"
