"""Seed data loading utilities for S3verless."""

import json
import logging
from pathlib import Path
from typing import Type

from aiobotocore.client import AioBaseClient

from s3verless.core.base import BaseS3Model
from s3verless.core.service import S3DataService

logger = logging.getLogger(__name__)


class SeedLoader:
    """Load and apply seed data from JSON files."""

    @staticmethod
    def load_from_file(file_path: Path | str) -> list[dict]:
        """Load seed data from a JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            List of dictionaries representing seed data

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file isn't valid JSON
        """
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return [data]

    @staticmethod
    async def seed_model(
        s3_client: AioBaseClient,
        model_class: Type[BaseS3Model],
        data: list[dict],
        bucket_name: str,
    ) -> int:
        """Seed a model with the provided data.

        Args:
            s3_client: The S3 client to use
            model_class: The model class to seed
            data: List of dictionaries with seed data
            bucket_name: The S3 bucket name

        Returns:
            Number of records successfully created
        """
        service = S3DataService(model_class, bucket_name)
        count = 0
        failed = 0
        for idx, item in enumerate(data):
            try:
                instance = model_class(**item)
                await service.create(s3_client, instance)
                count += 1
            except Exception as e:
                # Log and count failures but continue seeding
                failed += 1
                logger.warning(
                    f"Failed to seed {model_class.__name__} item {idx}: {e}"
                )
                continue

        if failed > 0:
            logger.info(
                f"Seeded {count} {model_class.__name__} records, {failed} failed"
            )
        return count

    @staticmethod
    async def clear_model(
        s3_client: AioBaseClient,
        model_class: Type[BaseS3Model],
        bucket_name: str,
    ) -> int:
        """Clear all existing data for a model.

        Args:
            s3_client: The S3 client to use
            model_class: The model class to clear
            bucket_name: The S3 bucket name

        Returns:
            Number of records deleted
        """
        service = S3DataService(model_class, bucket_name)
        count = 0

        # List all objects
        marker = None
        while True:
            objects, marker = await service.list_by_prefix(
                s3_client, limit=1000, marker=marker
            )
            for obj in objects:
                await service.delete(s3_client, obj.id)
                count += 1
            if not marker:
                break

        return count

    @staticmethod
    async def seed_from_file(
        s3_client: AioBaseClient,
        model_class: Type[BaseS3Model],
        file_path: Path | str,
        bucket_name: str,
        clear_existing: bool = False,
    ) -> dict:
        """Load and apply seed data from a JSON file.

        Args:
            s3_client: The S3 client to use
            model_class: The model class to seed
            file_path: Path to the JSON file
            bucket_name: The S3 bucket name
            clear_existing: Whether to clear existing data first

        Returns:
            Dictionary with seeding results (created, deleted counts)
        """
        deleted = 0
        if clear_existing:
            deleted = await SeedLoader.clear_model(s3_client, model_class, bucket_name)

        data = SeedLoader.load_from_file(file_path)
        created = await SeedLoader.seed_model(s3_client, model_class, data, bucket_name)

        return {
            "model": model_class.__name__,
            "file": str(file_path),
            "created": created,
            "deleted": deleted,
        }
