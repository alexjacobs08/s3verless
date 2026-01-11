"""Rate limiting for S3verless authentication endpoints.

This module provides a sliding window rate limiter that uses in-memory
storage with optional S3 persistence for distributed deployments.
"""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import HTTPException, Request, status

from s3verless.core.exceptions import S3RateLimitError


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule.

    Attributes:
        requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
        key_func: Function to extract the rate limit key from a request
        block_duration: How long to block after limit exceeded (seconds)
    """

    requests: int
    window_seconds: int
    key_func: str = "ip"  # "ip", "user", "ip_and_endpoint"
    block_duration: int = 0  # Additional block time after limit exceeded


@dataclass
class RateLimitEntry:
    """Tracks request timestamps for a single key."""

    timestamps: List[datetime] = field(default_factory=list)
    blocked_until: datetime | None = None


class RateLimiter:
    """In-memory sliding window rate limiter.

    This rate limiter uses a sliding window algorithm to track requests
    and enforce rate limits. It stores data in memory for fast access
    with optional periodic cleanup.
    """

    # Default rate limit configurations
    DEFAULT_LIMITS = {
        "login": RateLimitConfig(requests=5, window_seconds=60, block_duration=300),
        "register": RateLimitConfig(requests=3, window_seconds=3600),
        "refresh": RateLimitConfig(requests=10, window_seconds=60),
        "password_reset": RateLimitConfig(requests=3, window_seconds=3600),
        "default": RateLimitConfig(requests=100, window_seconds=60),
    }

    def __init__(
        self,
        limits: Dict[str, RateLimitConfig] | None = None,
        cleanup_interval: int = 300,
        trusted_proxies: List[str] | None = None,
        trust_x_forwarded_for: bool = False,
    ):
        """Initialize the rate limiter.

        Args:
            limits: Custom rate limit configurations
            cleanup_interval: How often to clean up expired entries (seconds)
            trusted_proxies: List of trusted proxy IPs that can set X-Forwarded-For
            trust_x_forwarded_for: If True, always trust X-Forwarded-For header.
                                   Only enable if behind a trusted reverse proxy.
        """
        self._storage: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = asyncio.Lock()
        self.limits = {**self.DEFAULT_LIMITS, **(limits or {})}
        self.cleanup_interval = cleanup_interval
        self._last_cleanup = datetime.now(timezone.utc)
        self.trusted_proxies = set(trusted_proxies or [])
        self.trust_x_forwarded_for = trust_x_forwarded_for

    def _get_key(
        self, request: Request, key_func: str, endpoint: str | None = None
    ) -> str:
        """Generate the rate limit key based on the key function.

        Args:
            request: The FastAPI request
            key_func: The key function to use
            endpoint: Optional endpoint name

        Returns:
            The rate limit key
        """
        # Get client IP from the connection
        direct_ip = request.client.host if request.client else "unknown"
        client_ip = direct_ip

        # Only trust X-Forwarded-For if explicitly enabled or from trusted proxy
        # This prevents attackers from spoofing their IP address
        if self.trust_x_forwarded_for or direct_ip in self.trusted_proxies:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # Take the leftmost (original client) IP
                client_ip = forwarded.split(",")[0].strip()

        if key_func == "ip":
            return f"ip:{client_ip}"
        elif key_func == "user":
            user = getattr(request.state, "current_user", None)
            if user:
                return f"user:{user.id}"
            return f"ip:{client_ip}"
        elif key_func == "ip_and_endpoint":
            return f"ip:{client_ip}:endpoint:{endpoint or request.url.path}"
        else:
            return f"ip:{client_ip}"

    async def check_rate_limit(
        self,
        request: Request,
        endpoint: str = "default",
    ) -> dict:
        """Check if a request is within rate limits.

        Args:
            request: The FastAPI request
            endpoint: The endpoint name for limit configuration

        Returns:
            Dict with remaining requests and reset time

        Raises:
            S3RateLimitError: If rate limit is exceeded
        """
        config = self.limits.get(endpoint, self.limits["default"])
        key = self._get_key(request, config.key_func, endpoint)

        async with self._lock:
            # Periodic cleanup
            await self._maybe_cleanup()

            entry = self._storage[key]
            now = datetime.now(timezone.utc)

            # Check if blocked
            if entry.blocked_until and entry.blocked_until > now:
                retry_after = int((entry.blocked_until - now).total_seconds())
                raise S3RateLimitError(
                    f"Too many requests. Try again in {retry_after} seconds.",
                    retry_after=retry_after,
                )

            # Clean old timestamps
            window_start = now - timedelta(seconds=config.window_seconds)
            entry.timestamps = [ts for ts in entry.timestamps if ts > window_start]

            # Check rate limit
            if len(entry.timestamps) >= config.requests:
                # Apply block duration if configured
                if config.block_duration > 0:
                    entry.blocked_until = now + timedelta(seconds=config.block_duration)
                    retry_after = config.block_duration
                else:
                    # Calculate when oldest request falls outside window
                    oldest = min(entry.timestamps)
                    retry_after = int(
                        (oldest + timedelta(seconds=config.window_seconds) - now).total_seconds()
                    )

                raise S3RateLimitError(
                    f"Rate limit exceeded. Maximum {config.requests} requests per {config.window_seconds} seconds.",
                    retry_after=max(1, retry_after),
                )

            # Add current timestamp
            entry.timestamps.append(now)

            # Calculate remaining requests and reset time
            remaining = config.requests - len(entry.timestamps)
            if entry.timestamps:
                reset_at = min(entry.timestamps) + timedelta(seconds=config.window_seconds)
                reset_seconds = int((reset_at - now).total_seconds())
            else:
                reset_seconds = config.window_seconds

            return {
                "remaining": remaining,
                "limit": config.requests,
                "reset_seconds": reset_seconds,
            }

    async def _maybe_cleanup(self) -> None:
        """Periodically clean up expired entries."""
        now = datetime.now(timezone.utc)
        if (now - self._last_cleanup).total_seconds() < self.cleanup_interval:
            return

        self._last_cleanup = now

        # Find keys to remove
        keys_to_remove = []
        for key, entry in self._storage.items():
            # Remove if no recent timestamps and not blocked
            if not entry.timestamps and (
                not entry.blocked_until or entry.blocked_until < now
            ):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._storage[key]

    def reset(self, key: str) -> None:
        """Reset rate limit for a specific key.

        Args:
            key: The rate limit key to reset
        """
        if key in self._storage:
            del self._storage[key]

    def reset_all(self) -> None:
        """Reset all rate limits (useful for testing)."""
        self._storage.clear()


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter.

    Returns:
        The RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set the global rate limiter (useful for testing).

    Args:
        limiter: The RateLimiter instance to use
    """
    global _rate_limiter
    _rate_limiter = limiter


def rate_limit(endpoint: str = "default"):
    """Decorator factory for rate limiting FastAPI endpoints.

    Args:
        endpoint: The endpoint name for limit configuration

    Returns:
        Dependency function for FastAPI

    Example:
        @app.post("/auth/login")
        async def login(
            rate_info: dict = Depends(rate_limit("login"))
        ):
            ...
    """

    async def check_limit(request: Request) -> dict:
        limiter = get_rate_limiter()
        return await limiter.check_rate_limit(request, endpoint)

    return check_limit


class RateLimitMiddleware:
    """FastAPI middleware for global rate limiting.

    This middleware applies rate limiting to all requests or
    specific path patterns.
    """

    def __init__(
        self,
        app,
        limiter: RateLimiter | None = None,
        exclude_paths: List[str] | None = None,
        endpoint_mapping: Dict[str, str] | None = None,
    ):
        """Initialize the middleware.

        Args:
            app: The FastAPI application
            limiter: Custom RateLimiter instance
            exclude_paths: Paths to exclude from rate limiting
            endpoint_mapping: Map paths to endpoint names for limit config
        """
        self.app = app
        self.limiter = limiter or get_rate_limiter()
        self.exclude_paths = set(exclude_paths or ["/health", "/docs", "/openapi.json"])
        self.endpoint_mapping = endpoint_mapping or {
            "/auth/token": "login",
            "/auth/login": "login",
            "/auth/register": "register",
            "/auth/refresh": "refresh",
        }

    async def __call__(self, scope, receive, send):
        """ASGI middleware interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]

        # Skip excluded paths
        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        # Determine endpoint name
        endpoint = self.endpoint_mapping.get(path, "default")

        # Create a minimal request object for rate limiting
        from starlette.requests import Request

        request = Request(scope, receive)

        try:
            rate_info = await self.limiter.check_rate_limit(request, endpoint)

            # Add rate limit headers
            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.extend([
                        (b"X-RateLimit-Limit", str(rate_info["limit"]).encode()),
                        (b"X-RateLimit-Remaining", str(rate_info["remaining"]).encode()),
                        (b"X-RateLimit-Reset", str(rate_info["reset_seconds"]).encode()),
                    ])
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_with_headers)

        except S3RateLimitError as e:
            # Return 429 response
            response_body = json.dumps({
                "error": "rate_limit_exceeded",
                "message": e.message,
                "retry_after": e.retry_after,
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(e.retry_after or 60).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": response_body,
            })
