"""Migration system for S3verless.

This module provides a migration system for evolving data schemas
stored in S3. Unlike traditional database migrations, S3verless
migrations transform JSON data in place.
"""

from s3verless.migrations.base import Migration, MigrationOperation
from s3verless.migrations.runner import MigrationRunner
from s3verless.migrations.operations import (
    AddField,
    RemoveField,
    RenameField,
    TransformField,
    RenameModel,
)

__all__ = [
    "Migration",
    "MigrationOperation",
    "MigrationRunner",
    "AddField",
    "RemoveField",
    "RenameField",
    "TransformField",
    "RenameModel",
]
