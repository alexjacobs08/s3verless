"""Tests for auth security features (blacklist, rate limiting)."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from s3verless.auth.blacklist import TokenBlacklist, get_blacklist
from s3verless.auth.rate_limit import RateLimiter, RateLimitConfig
from s3verless.core.exceptions import S3RateLimitError


class TestTokenBlacklist:
    """Tests for TokenBlacklist."""

    @pytest.fixture
    def mock_s3(self):
        """Create a mock S3 client."""
        from s3verless.testing.mocks import InMemoryS3
        return InMemoryS3()

    @pytest.fixture
    def blacklist(self):
        """Create a blacklist instance."""
        return TokenBlacklist(bucket_name="test-bucket", cache_ttl_seconds=60)

    @pytest.mark.asyncio
    async def test_add_and_check_blacklisted(self, blacklist, mock_s3):
        """Test adding a token to blacklist and checking it."""
        jti = "test-jti-12345"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await blacklist.add(mock_s3, jti, expires_at)

        # Give async task time to complete
        await asyncio.sleep(0.1)

        is_blacklisted = await blacklist.is_blacklisted(mock_s3, jti)
        assert is_blacklisted is True

    @pytest.mark.asyncio
    async def test_non_blacklisted_token(self, blacklist, mock_s3):
        """Test checking a token that is not blacklisted."""
        is_blacklisted = await blacklist.is_blacklisted(mock_s3, "unknown-jti")
        assert is_blacklisted is False

    @pytest.mark.asyncio
    async def test_blacklist_uses_cache(self, blacklist, mock_s3):
        """Test that blacklist uses in-memory cache."""
        jti = "cached-jti"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await blacklist.add(mock_s3, jti, expires_at)

        # Should be in cache immediately (before S3 persistence)
        assert jti in blacklist._cache

    @pytest.mark.asyncio
    async def test_multiple_tokens(self, blacklist, mock_s3):
        """Test blacklisting multiple tokens."""
        jti1 = "jti-1"
        jti2 = "jti-2"
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        await blacklist.add(mock_s3, jti1, expires)
        await blacklist.add(mock_s3, jti2, expires)

        assert await blacklist.is_blacklisted(mock_s3, jti1) is True
        assert await blacklist.is_blacklisted(mock_s3, jti2) is True


class TestGetBlacklist:
    """Tests for get_blacklist singleton."""

    def test_returns_same_instance(self):
        """Test that get_blacklist returns singleton."""
        # Reset for clean test
        import s3verless.auth.blacklist as blacklist_module
        original = blacklist_module._blacklist
        blacklist_module._blacklist = None

        try:
            bl1 = get_blacklist("test-bucket-singleton")
            bl2 = get_blacklist("test-bucket-singleton")

            assert bl1 is bl2
        finally:
            blacklist_module._blacklist = original

    def test_get_blacklist_creates_instance(self):
        """Test that get_blacklist creates an instance with the bucket name."""
        import s3verless.auth.blacklist as blacklist_module
        original = blacklist_module._blacklist
        blacklist_module._blacklist = None

        try:
            bl = get_blacklist("my-bucket")
            assert bl.bucket_name == "my-bucket"
        finally:
            blacklist_module._blacklist = original


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter instance."""
        return RateLimiter()

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {}
        request.state = MagicMock()
        request.url = MagicMock()
        request.url.path = "/test"
        return request

    @pytest.mark.asyncio
    async def test_allows_within_limit(self, rate_limiter, mock_request):
        """Test that requests within limit are allowed."""
        # Use a custom config with known limits
        rate_limiter.limits["test_endpoint"] = RateLimitConfig(requests=5, window_seconds=60)

        for _ in range(5):
            result = await rate_limiter.check_rate_limit(mock_request, "test_endpoint")
            assert "remaining" in result

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, rate_limiter, mock_request):
        """Test that requests over limit raise S3RateLimitError."""
        rate_limiter.limits["test_limit"] = RateLimitConfig(requests=2, window_seconds=60)

        # Use up the limit
        await rate_limiter.check_rate_limit(mock_request, "test_limit")
        await rate_limiter.check_rate_limit(mock_request, "test_limit")

        # Next request should raise
        with pytest.raises(S3RateLimitError):
            await rate_limiter.check_rate_limit(mock_request, "test_limit")

    @pytest.mark.asyncio
    async def test_remaining_count(self, rate_limiter, mock_request):
        """Test remaining count is correct."""
        rate_limiter.limits["count_test"] = RateLimitConfig(requests=5, window_seconds=60)

        result = await rate_limiter.check_rate_limit(mock_request, "count_test")
        assert result["remaining"] == 4

        result = await rate_limiter.check_rate_limit(mock_request, "count_test")
        assert result["remaining"] == 3

    @pytest.mark.asyncio
    async def test_different_endpoints_separate_limits(self, mock_request):
        """Test that different endpoints have separate rate limits when using ip_and_endpoint key."""
        rate_limiter = RateLimiter()
        # Use ip_and_endpoint key function so endpoints have separate limits
        rate_limiter.limits["endpoint1"] = RateLimitConfig(
            requests=2, window_seconds=60, key_func="ip_and_endpoint"
        )
        rate_limiter.limits["endpoint2"] = RateLimitConfig(
            requests=2, window_seconds=60, key_func="ip_and_endpoint"
        )

        # Use up limit on endpoint1
        await rate_limiter.check_rate_limit(mock_request, "endpoint1")
        await rate_limiter.check_rate_limit(mock_request, "endpoint1")

        # endpoint2 should still allow requests because it uses a different key
        result = await rate_limiter.check_rate_limit(mock_request, "endpoint2")
        assert "remaining" in result

    @pytest.mark.asyncio
    async def test_different_ips_separate_limits(self):
        """Test that different IPs have separate rate limits."""
        rate_limiter = RateLimiter()
        rate_limiter.limits["ip_test"] = RateLimitConfig(requests=2, window_seconds=60)

        request1 = MagicMock()
        request1.client = MagicMock()
        request1.client.host = "192.168.1.1"
        request1.headers = {}
        request1.state = MagicMock()
        request1.url = MagicMock()
        request1.url.path = "/test"

        request2 = MagicMock()
        request2.client = MagicMock()
        request2.client.host = "192.168.1.2"
        request2.headers = {}
        request2.state = MagicMock()
        request2.url = MagicMock()
        request2.url.path = "/test"

        # Use up limit for IP1
        await rate_limiter.check_rate_limit(request1, "ip_test")
        await rate_limiter.check_rate_limit(request1, "ip_test")

        # IP2 should still allow requests
        result = await rate_limiter.check_rate_limit(request2, "ip_test")
        assert "remaining" in result

    @pytest.mark.asyncio
    async def test_block_duration(self, mock_request):
        """Test block duration when limit exceeded."""
        rate_limiter = RateLimiter()
        rate_limiter.limits["block_test"] = RateLimitConfig(
            requests=1, window_seconds=60, block_duration=300
        )

        await rate_limiter.check_rate_limit(mock_request, "block_test")

        with pytest.raises(S3RateLimitError) as exc_info:
            await rate_limiter.check_rate_limit(mock_request, "block_test")

        assert exc_info.value.retry_after > 0

    def test_default_limits(self, rate_limiter):
        """Test default rate limits exist."""
        assert "login" in RateLimiter.DEFAULT_LIMITS
        assert "register" in RateLimiter.DEFAULT_LIMITS
        assert "default" in RateLimiter.DEFAULT_LIMITS

    def test_reset_limit(self, rate_limiter, mock_request):
        """Test resetting rate limit for a key."""
        key = "ip:127.0.0.1"
        rate_limiter._storage[key].timestamps = [datetime.now(timezone.utc)]

        rate_limiter.reset(key)

        assert key not in rate_limiter._storage

    def test_reset_all(self, rate_limiter):
        """Test resetting all rate limits."""
        rate_limiter._storage["key1"].timestamps = [datetime.now(timezone.utc)]
        rate_limiter._storage["key2"].timestamps = [datetime.now(timezone.utc)]

        rate_limiter.reset_all()

        assert len(rate_limiter._storage) == 0


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_block_duration(self):
        """Test default block duration is 0."""
        config = RateLimitConfig(requests=5, window_seconds=60)
        assert config.block_duration == 0

    def test_custom_block_duration(self):
        """Test custom block duration."""
        config = RateLimitConfig(requests=5, window_seconds=60, block_duration=600)
        assert config.block_duration == 600

    def test_default_key_func(self):
        """Test default key function is ip."""
        config = RateLimitConfig(requests=5, window_seconds=60)
        assert config.key_func == "ip"
