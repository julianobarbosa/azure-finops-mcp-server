"""Cache management for Azure FinOps API responses."""

import hashlib
import json
import logging
import time
from datetime import date
from functools import wraps
from typing import Any, Callable, Dict, Optional

from azure_finops_mcp_server.config import get_config

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage caching of API responses to reduce Azure API calls."""

    def __init__(self, ttl_seconds: Optional[int] = None):
        """
        Initialize cache manager.

        Args:
            ttl_seconds: Time to live for cache entries (uses config default if not specified)
        """
        config = get_config()
        self.ttl_seconds = ttl_seconds or config.cache_ttl_seconds
        self.enabled = config.enable_caching
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _generate_key(self, prefix: str, **kwargs) -> str:
        """
        Generate a cache key from prefix and parameters.

        Args:
            prefix: Cache key prefix
            **kwargs: Parameters to include in key

        Returns:
            Cache key string
        """
        # Sort kwargs for consistent key generation
        sorted_params = sorted(kwargs.items())
        key_data = f"{prefix}:{json.dumps(sorted_params)}"

        # Use SHA-256 hash for long keys to ensure consistent key generation
        if len(key_data) > 100:
            key_hash = hashlib.sha256(key_data.encode()).hexdigest()
            return f"{prefix}:{key_hash}"

        return key_data

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None

        if key in self._cache:
            entry = self._cache[key]

            # Check if expired
            if time.time() < entry["expires_at"]:
                self._stats["hits"] += 1
                logger.debug(f"Cache hit for key: {key}")
                return entry["value"]
            else:
                # Remove expired entry
                del self._cache[key]
                self._stats["evictions"] += 1
                logger.debug(f"Cache expired for key: {key}")

        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override in seconds
        """
        if not self.enabled:
            return

        ttl_to_use = ttl or self.ttl_seconds
        self._cache[key] = {"value": value, "expires_at": time.time() + ttl_to_use, "created_at": time.time()}
        logger.debug(f"Cached value for key: {key} (TTL: {ttl_to_use}s)")

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Deleted cache key: {key}")
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} cache entries")

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [key for key, entry in self._cache.items() if current_time >= entry["expires_at"]]

        for key in expired_keys:
            del self._cache[key]
            self._stats["evictions"] += 1

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate": round(hit_rate, 2),
            "total_requests": total_requests,
            "current_entries": len(self._cache),
            "enabled": self.enabled,
        }


# Global cache instance
_cache: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """
    Get the global cache manager instance.

    Returns:
        CacheManager instance
    """
    global _cache

    if _cache is None:
        _cache = CacheManager()

    return _cache


def reset_cache() -> None:
    """Reset the global cache instance."""
    global _cache
    if _cache:
        _cache.clear()
    _cache = None


def cached(prefix: str, ttl: Optional[int] = None):
    """
    Decorator for caching function results.

    Args:
        prefix: Cache key prefix
        ttl: Optional TTL override

    Returns:
        Decorated function with caching
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key from function arguments
            # Skip credential argument if present
            cache_kwargs = {k: v for k, v in kwargs.items() if k not in ["credential", "client"]}

            # Include relevant args (skip credential/client objects)
            cache_args = []
            for arg in args:
                if not hasattr(arg, "__module__") or "azure" not in arg.__module__:
                    cache_args.append(str(arg))

            cache_key = cache._generate_key(prefix, args=cache_args, **cache_kwargs)

            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


class RegionCache:
    """Specialized cache for region-specific data."""

    def __init__(self):
        """Initialize region cache."""
        self._cache = {}
        self._ttl = 300  # 5 minutes default

    def get_or_fetch(self, subscription_id: str, region: str, resource_type: str, fetch_func: Callable) -> Any:
        """
        Get cached data or fetch if not available.

        Args:
            subscription_id: Azure subscription ID
            region: Azure region
            resource_type: Type of resource (vms, disks, ips)
            fetch_func: Function to fetch data if not cached

        Returns:
            Cached or fetched data
        """
        cache_key = f"{subscription_id}:{region}:{resource_type}"

        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if time.time() < entry["expires_at"]:
                logger.debug(f"Region cache hit: {cache_key}")
                return entry["data"]

        # Fetch and cache
        logger.debug(f"Region cache miss: {cache_key}")
        data = fetch_func()

        self._cache[cache_key] = {"data": data, "expires_at": time.time() + self._ttl}

        return data

    def invalidate_region(self, subscription_id: str, region: str) -> None:
        """
        Invalidate all cache entries for a region.

        Args:
            subscription_id: Azure subscription ID
            region: Azure region to invalidate
        """
        keys_to_delete = [key for key in self._cache.keys() if key.startswith(f"{subscription_id}:{region}:")]

        for key in keys_to_delete:
            del self._cache[key]

        logger.debug(f"Invalidated {len(keys_to_delete)} cache entries for region {region}")


class CostDataCache:
    """Specialized cache for cost data with date-aware TTL."""

    def __init__(self):
        """Initialize cost data cache."""
        self._cache = {}

    def get_ttl_for_period(self, start_date: date, end_date: date) -> int:
        """
        Calculate appropriate TTL based on date range.

        Args:
            start_date: Period start date
            end_date: Period end date

        Returns:
            TTL in seconds
        """
        today = date.today()

        # If period is complete (ended in the past), cache longer
        if end_date < today:
            return 86400  # 24 hours for historical data

        # If period includes today, cache shorter
        if start_date <= today <= end_date:
            return 900  # 15 minutes for current data

        # Future period (shouldn't happen but handle it)
        return 300  # 5 minutes

    def cache_cost_data(self, subscription_id: str, start_date: date, end_date: date, data: Dict[str, Any]) -> None:
        """
        Cache cost data with appropriate TTL.

        Args:
            subscription_id: Azure subscription ID
            start_date: Cost period start
            end_date: Cost period end
            data: Cost data to cache
        """
        cache_key = f"cost:{subscription_id}:{start_date}:{end_date}"
        ttl = self.get_ttl_for_period(start_date, end_date)

        cache = get_cache()
        cache.set(cache_key, data, ttl)

        logger.debug(f"Cached cost data for {subscription_id} ({start_date} to {end_date}) with TTL {ttl}s")
