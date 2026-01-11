"""Token blacklist for immediate access token revocation.

This module provides a hybrid in-memory/S3 token blacklist for
revoking access tokens before they expire.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Set

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class TokenBlacklist:
    """Token blacklist with in-memory cache and S3 persistence.

    This class maintains a fast in-memory cache of blacklisted token IDs
    (JTI claims) with periodic persistence to S3. This allows for fast
    checking while still providing durability across restarts.

    The blacklist automatically cleans up expired entries to prevent
    unbounded growth.
    """

    def __init__(
        self,
        bucket_name: str,
        cache_ttl_seconds: int = 300,
        blacklist_key: str = "_system/token_blacklist.json",
    ):
        """Initialize the token blacklist.

        Args:
            bucket_name: S3 bucket name for persistence
            cache_ttl_seconds: How long to cache the blacklist in memory
            blacklist_key: S3 key for storing the blacklist
        """
        self._cache: Set[str] = set()
        self._cache_expires: datetime | None = None
        self.bucket_name = bucket_name
        self.cache_ttl_seconds = cache_ttl_seconds
        self._blacklist_key = blacklist_key
        self._lock = asyncio.Lock()

    async def add(
        self,
        s3_client,
        token_jti: str,
        expires_at: datetime,
    ) -> None:
        """Add a token to the blacklist.

        Args:
            s3_client: The S3 client to use
            token_jti: The JWT ID (jti claim) of the token
            expires_at: When the token expires (for cleanup)
        """
        async with self._lock:
            # Add to cache immediately
            self._cache.add(token_jti)

        # Persist to S3 and await the result for durability
        try:
            await self._persist_entry(s3_client, token_jti, expires_at)
        except Exception as e:
            # Log the error but keep the entry in cache
            # On restart, this token won't be blacklisted, but that's
            # better than silently failing
            logger.error(f"Failed to persist blacklist entry for {token_jti}: {e}")

    async def is_blacklisted(
        self,
        s3_client,
        token_jti: str,
    ) -> bool:
        """Check if a token is blacklisted.

        Args:
            s3_client: The S3 client to use
            token_jti: The JWT ID to check

        Returns:
            True if the token is blacklisted, False otherwise
        """
        # Check cache first
        if token_jti in self._cache:
            return True

        # Refresh cache if expired
        if self._cache_expired():
            await self._load_from_s3(s3_client)

        return token_jti in self._cache

    def _cache_expired(self) -> bool:
        """Check if the cache has expired."""
        if self._cache_expires is None:
            return True
        return datetime.now(timezone.utc) > self._cache_expires

    async def _load_from_s3(self, s3_client) -> None:
        """Load the blacklist from S3."""
        async with self._lock:
            try:
                response = await s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=self._blacklist_key,
                )
                body = await response["Body"].read()
                data = json.loads(body.decode("utf-8"))

                # Filter out expired entries
                now = datetime.now(timezone.utc)
                self._cache = {
                    entry["jti"]
                    for entry in data.get("entries", [])
                    if datetime.fromisoformat(entry["expires_at"]) > now
                }

                self._cache_expires = now + timedelta(seconds=self.cache_ttl_seconds)
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    # Blacklist doesn't exist yet
                    self._cache = set()
                    self._cache_expires = datetime.now(timezone.utc) + timedelta(
                        seconds=self.cache_ttl_seconds
                    )
                else:
                    # Log error but keep existing cache data if available
                    logger.error(f"S3 error loading blacklist: {e}")
                    # Don't clear cache on error - keep stale data rather than lose blacklist
                    if self._cache_expires is None:
                        # First load failed, set a short retry interval
                        self._cache_expires = datetime.now(timezone.utc) + timedelta(seconds=30)
            except Exception as e:
                # Log unexpected errors
                logger.error(f"Unexpected error loading blacklist: {e}")
                # Don't clear cache - keep stale data if available
                if self._cache_expires is None:
                    self._cache_expires = datetime.now(timezone.utc) + timedelta(seconds=30)

    async def _persist_entry(
        self,
        s3_client,
        token_jti: str,
        expires_at: datetime,
    ) -> None:
        """Persist a blacklist entry to S3."""
        try:
            # Load current blacklist
            try:
                response = await s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=self._blacklist_key,
                )
                body = await response["Body"].read()
                data = json.loads(body.decode("utf-8"))
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    data = {"entries": []}
                else:
                    raise

            # Add new entry
            data["entries"].append({
                "jti": token_jti,
                "expires_at": expires_at.isoformat(),
                "revoked_at": datetime.now(timezone.utc).isoformat(),
            })

            # Clean up expired entries
            now = datetime.now(timezone.utc)
            data["entries"] = [
                entry
                for entry in data["entries"]
                if datetime.fromisoformat(entry["expires_at"]) > now
            ]

            # Save back to S3
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=self._blacklist_key,
                Body=json.dumps(data).encode("utf-8"),
                ContentType="application/json",
            )
        except ClientError as e:
            logger.error(f"S3 error persisting blacklist entry: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error persisting blacklist entry: {e}")
            raise

    async def cleanup(self, s3_client) -> int:
        """Clean up expired entries from the blacklist.

        Args:
            s3_client: The S3 client to use

        Returns:
            Number of entries removed
        """
        try:
            response = await s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self._blacklist_key,
            )
            body = await response["Body"].read()
            data = json.loads(body.decode("utf-8"))

            original_count = len(data.get("entries", []))

            # Filter out expired entries
            now = datetime.now(timezone.utc)
            data["entries"] = [
                entry
                for entry in data.get("entries", [])
                if datetime.fromisoformat(entry["expires_at"]) > now
            ]

            removed_count = original_count - len(data["entries"])

            # Save cleaned data
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=self._blacklist_key,
                Body=json.dumps(data).encode("utf-8"),
                ContentType="application/json",
            )

            # Update cache
            self._cache = {entry["jti"] for entry in data["entries"]}
            self._cache_expires = now + timedelta(seconds=self.cache_ttl_seconds)

            return removed_count
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return 0
            raise

    def clear_cache(self) -> None:
        """Clear the in-memory cache (useful for testing)."""
        self._cache.clear()
        self._cache_expires = None


# Global blacklist instance (initialized by app)
_blacklist: TokenBlacklist | None = None


def get_blacklist(bucket_name: str | None = None) -> TokenBlacklist:
    """Get or create the global token blacklist.

    Args:
        bucket_name: S3 bucket name (required on first call)

    Returns:
        The TokenBlacklist instance
    """
    global _blacklist
    if _blacklist is None:
        if bucket_name is None:
            raise ValueError("bucket_name required on first call")
        _blacklist = TokenBlacklist(bucket_name)
    return _blacklist


def set_blacklist(blacklist: TokenBlacklist) -> None:
    """Set the global token blacklist (useful for testing).

    Args:
        blacklist: The TokenBlacklist instance to use
    """
    global _blacklist
    _blacklist = blacklist
