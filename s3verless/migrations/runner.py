"""Migration runner for S3verless."""

import importlib.util
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from botocore.exceptions import ClientError

from s3verless.migrations.base import Migration, MigrationRecord

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Runs migrations against S3-stored data.

    This runner:
    - Tracks which migrations have been applied
    - Loads migrations from Python files
    - Applies pending migrations in order
    - Supports rollback of applied migrations
    """

    MIGRATION_HISTORY_KEY = "_system/migration_history.json"

    def __init__(
        self,
        s3_client,
        bucket_name: str,
        migrations_dir: Path | None = None,
    ):
        """Initialize the migration runner.

        Args:
            s3_client: The S3 client to use
            bucket_name: The S3 bucket name
            migrations_dir: Directory containing migration files
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.migrations_dir = migrations_dir
        self._migrations: List[Migration] = []
        self._loaded = False

    def _load_migrations(self) -> None:
        """Load migrations from the migrations directory."""
        if self._loaded:
            return

        if not self.migrations_dir or not self.migrations_dir.exists():
            self._loaded = True
            return

        # Find all migration files
        migration_files = sorted(self.migrations_dir.glob("*.py"))

        for file_path in migration_files:
            if file_path.name.startswith("_"):
                continue

            # Load the module
            spec = importlib.util.spec_from_file_location(
                f"migration_{file_path.stem}",
                file_path,
            )
            if not spec or not spec.loader:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"migration_{file_path.stem}"] = module

            try:
                spec.loader.exec_module(module)

                # Look for Migration instances in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, Migration):
                        self._migrations.append(attr)
            except Exception as e:
                logger.warning(f"Failed to load migration from {file_path}: {e}")
                continue

        # Sort by version
        self._migrations.sort(key=lambda m: m.version)
        self._loaded = True

    def register(self, migration: Migration) -> None:
        """Register a migration programmatically.

        Args:
            migration: The migration to register
        """
        self._migrations.append(migration)
        self._migrations.sort(key=lambda m: m.version)

    async def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions.

        Returns:
            List of applied version strings
        """
        try:
            response = await self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self.MIGRATION_HISTORY_KEY,
            )
            body = await response["Body"].read()
            data = json.loads(body.decode("utf-8"))
            return [r["version"] for r in data.get("records", [])]
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                logger.warning(f"Failed to load migration history: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error loading migration history: {e}")
            return []

    async def _save_migration_record(self, record: MigrationRecord) -> None:
        """Save a migration record to S3."""
        # Load existing records
        try:
            response = await self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self.MIGRATION_HISTORY_KEY,
            )
            body = await response["Body"].read()
            data = json.loads(body.decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                logger.warning(f"Failed to load migration records: {e}")
            data = {"records": []}
        except Exception as e:
            logger.warning(f"Unexpected error loading migration records: {e}")
            data = {"records": []}

        # Add new record
        data["records"].append(record.to_dict())

        # Save back
        await self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.MIGRATION_HISTORY_KEY,
            Body=json.dumps(data).encode("utf-8"),
            ContentType="application/json",
        )

    async def _remove_migration_record(self, version: str) -> None:
        """Remove a migration record (for rollback)."""
        try:
            response = await self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self.MIGRATION_HISTORY_KEY,
            )
            body = await response["Body"].read()
            data = json.loads(body.decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                logger.warning(f"Failed to load migration records for removal: {e}")
            return
        except Exception as e:
            logger.warning(f"Unexpected error loading migration records for removal: {e}")
            return

        # Remove the record
        data["records"] = [
            r for r in data.get("records", [])
            if r["version"] != version
        ]

        # Save back
        await self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.MIGRATION_HISTORY_KEY,
            Body=json.dumps(data).encode("utf-8"),
            ContentType="application/json",
        )

    def get_pending_migrations(self) -> List[Migration]:
        """Get list of migrations that haven't been applied.

        Returns:
            List of pending Migration objects
        """
        self._load_migrations()
        return self._migrations

    async def run_pending(self) -> List[dict]:
        """Run all pending migrations.

        Returns:
            List of results for each applied migration
        """
        self._load_migrations()
        applied = await self.get_applied_migrations()

        results = []
        for migration in self._migrations:
            if migration.version in applied:
                continue

            result = await self._apply_migration(migration)
            results.append(result)

        return results

    async def _apply_migration(self, migration: Migration) -> dict:
        """Apply a single migration.

        Args:
            migration: The migration to apply

        Returns:
            Dictionary with migration results
        """
        from s3verless.core.registry import get_model_by_name

        # Get the model
        model = get_model_by_name(migration.model_name)
        if not model:
            # Migration for unknown model - just record it
            record = MigrationRecord(
                version=migration.version,
                model_name=migration.model_name,
                description=migration.description,
                objects_transformed=0,
            )
            await self._save_migration_record(record)
            return {
                "version": migration.version,
                "description": migration.description,
                "status": "skipped",
                "reason": f"Model '{migration.model_name}' not found",
            }

        # Get model prefix
        prefix = model.get_s3_prefix()

        # List all objects for this model
        objects_transformed = 0
        continuation_token = None

        while True:
            params = {
                "Bucket": self.bucket_name,
                "Prefix": prefix,
                "MaxKeys": 100,
            }
            if continuation_token:
                params["ContinuationToken"] = continuation_token

            response = await self.s3_client.list_objects_v2(**params)

            if "Contents" not in response:
                break

            for obj_summary in response["Contents"]:
                key = obj_summary["Key"]
                if not key.endswith(".json"):
                    continue

                # Load object
                try:
                    obj_response = await self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=key,
                    )
                    body = await obj_response["Body"].read()
                    data = json.loads(body.decode("utf-8"))
                except Exception as e:
                    logger.warning(f"Failed to load object {key} during migration {migration.version}: {e}")
                    continue

                # Apply migration
                try:
                    new_data = migration.apply(data)
                except Exception as e:
                    logger.error(f"Migration {migration.version} failed on object {key}: {e}")
                    continue

                # Save transformed object
                await self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=json.dumps(new_data).encode("utf-8"),
                    ContentType="application/json",
                )
                objects_transformed += 1

            if not response.get("IsTruncated", False):
                break

            continuation_token = response.get("NextContinuationToken")

        # Record the migration
        record = MigrationRecord(
            version=migration.version,
            model_name=migration.model_name,
            description=migration.description,
            objects_transformed=objects_transformed,
        )
        await self._save_migration_record(record)

        return {
            "version": migration.version,
            "description": migration.description,
            "status": "applied",
            "objects_transformed": objects_transformed,
        }

    async def rollback(self, version: str) -> dict:
        """Rollback a specific migration.

        Args:
            version: The version to rollback

        Returns:
            Dictionary with rollback results

        Raises:
            ValueError: If migration not found or not reversible
        """
        self._load_migrations()

        # Find the migration
        migration = next(
            (m for m in self._migrations if m.version == version),
            None,
        )
        if not migration:
            raise ValueError(f"Migration '{version}' not found")

        if not migration.reversible:
            raise ValueError(f"Migration '{version}' is not reversible")

        # Check if it was applied
        applied = await self.get_applied_migrations()
        if version not in applied:
            raise ValueError(f"Migration '{version}' has not been applied")

        from s3verless.core.registry import get_model_by_name

        model = get_model_by_name(migration.model_name)
        if not model:
            # Just remove the record
            await self._remove_migration_record(version)
            return {
                "version": version,
                "description": migration.description,
                "status": "rolled_back",
                "objects_transformed": 0,
            }

        # Get model prefix
        prefix = model.get_s3_prefix()

        # Rollback all objects
        objects_transformed = 0
        continuation_token = None

        while True:
            params = {
                "Bucket": self.bucket_name,
                "Prefix": prefix,
                "MaxKeys": 100,
            }
            if continuation_token:
                params["ContinuationToken"] = continuation_token

            response = await self.s3_client.list_objects_v2(**params)

            if "Contents" not in response:
                break

            for obj_summary in response["Contents"]:
                key = obj_summary["Key"]
                if not key.endswith(".json"):
                    continue

                # Load object
                try:
                    obj_response = await self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=key,
                    )
                    body = await obj_response["Body"].read()
                    data = json.loads(body.decode("utf-8"))
                except Exception as e:
                    logger.warning(f"Failed to load object {key} during rollback {migration.version}: {e}")
                    continue

                # Apply rollback
                try:
                    new_data = migration.rollback(data)
                except Exception as e:
                    logger.error(f"Rollback {migration.version} failed on object {key}: {e}")
                    continue

                # Save rolled-back object
                await self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=json.dumps(new_data).encode("utf-8"),
                    ContentType="application/json",
                )
                objects_transformed += 1

            if not response.get("IsTruncated", False):
                break

            continuation_token = response.get("NextContinuationToken")

        # Remove the migration record
        await self._remove_migration_record(version)

        return {
            "version": version,
            "description": migration.description,
            "status": "rolled_back",
            "objects_transformed": objects_transformed,
        }
