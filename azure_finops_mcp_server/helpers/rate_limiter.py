"""Rate limiting implementation for Azure API calls."""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    enabled: bool = True
    requests_per_second: float = 10.0
    burst_size: int = 20
    window_seconds: int = 60
    per_subscription: bool = True


class TokenBucket:
    """Token bucket algorithm for rate limiting."""

    def __init__(self, rate: float, capacity: int):
        """
        Initialize token bucket.

        Args:
            rate: Tokens added per second
            capacity: Maximum bucket capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        """Refill bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_update = now


class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limiting configuration
        """
        self.config = config or RateLimitConfig()
        self.buckets: Dict[str, TokenBucket] = {}
        self.request_history: Dict[str, deque] = {}
        self.lock = threading.Lock()

        if not self.config.enabled:
            logger.info("Rate limiting is disabled")

    def acquire(self, key: Optional[str] = None, tokens: int = 1) -> bool:
        """
        Acquire permission to make API call.

        Args:
            key: Optional key for per-resource limiting (e.g., subscription ID)
            tokens: Number of tokens to consume

        Returns:
            True if request is allowed, False if rate limited
        """
        if not self.config.enabled:
            return True

        bucket_key = key if self.config.per_subscription and key else "global"

        with self.lock:
            if bucket_key not in self.buckets:
                self.buckets[bucket_key] = TokenBucket(
                    rate=self.config.requests_per_second, capacity=self.config.burst_size
                )

            bucket = self.buckets[bucket_key]

        # Try to consume tokens
        if bucket.consume(tokens):
            self._record_request(bucket_key)
            return True

        logger.warning(f"Rate limit exceeded for {bucket_key}")
        return False

    def wait_if_needed(self, key: Optional[str] = None, tokens: int = 1) -> None:
        """
        Wait if necessary to respect rate limits.

        Args:
            key: Optional key for per-resource limiting
            tokens: Number of tokens to consume
        """
        if not self.config.enabled:
            return

        while not self.acquire(key, tokens):
            # Wait for tokens to refill
            wait_time = 1.0 / self.config.requests_per_second
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            time.sleep(wait_time)

    def _record_request(self, key: str):
        """Record request timestamp for monitoring."""
        if key not in self.request_history:
            self.request_history[key] = deque(maxlen=1000)

        self.request_history[key].append(time.time())

    def get_stats(self, key: Optional[str] = None) -> Dict[str, float]:
        """
        Get rate limiting statistics.

        Args:
            key: Optional key to get stats for

        Returns:
            Dictionary with rate limiting statistics
        """
        stats: Dict[str, float] = {}

        if not self.config.enabled:
            return {"enabled": 0.0}  # Return float for consistency

        bucket_key = key if self.config.per_subscription and key else "global"

        if bucket_key in self.buckets:
            bucket = self.buckets[bucket_key]
            with bucket.lock:
                bucket._refill()
                stats["tokens_available"] = float(bucket.tokens)
                stats["capacity"] = float(bucket.capacity)
                stats["rate"] = float(bucket.rate)

        if bucket_key in self.request_history:
            history = self.request_history[bucket_key]
            if history:
                now = time.time()
                recent_requests = sum(1 for t in history if now - t < self.config.window_seconds)
                stats["recent_requests"] = float(recent_requests)
                stats["requests_per_second"] = float(recent_requests) / float(self.config.window_seconds)

        return stats

    def reset(self, key: Optional[str] = None):
        """
        Reset rate limiter for a specific key or all keys.

        Args:
            key: Optional key to reset, or None to reset all
        """
        with self.lock:
            if key:
                if key in self.buckets:
                    del self.buckets[key]
                if key in self.request_history:
                    del self.request_history[key]
            else:
                self.buckets.clear()
                self.request_history.clear()

        logger.info(f"Rate limiter reset for {key or 'all keys'}")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter

    if _rate_limiter is None:
        from azure_finops_mcp_server.config import get_config

        config = get_config()

        rate_config = RateLimitConfig(
            enabled=config.rate_limit_enabled,
            requests_per_second=config.rate_limit_requests_per_second,
            burst_size=config.rate_limit_burst_size,
            window_seconds=config.rate_limit_window_seconds,
            per_subscription=config.rate_limit_per_subscription,
        )

        _rate_limiter = RateLimiter(rate_config)

    return _rate_limiter


def reset_rate_limiter():
    """Reset global rate limiter."""
    global _rate_limiter
    _rate_limiter = None
