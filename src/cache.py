"""
Smart Home Assistant - Cache Module

In-memory caching system with TTL support, LRU eviction, and statistics tracking.
Reduces API costs and latency by caching Home Assistant state queries and repeated requests.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import time
from collections import OrderedDict
from threading import Lock
from typing import Any


class CacheManager:
    """
    Thread-safe in-memory cache with TTL and LRU eviction.

    Features:
    - Time-based expiration (TTL)
    - Size-based eviction (LRU)
    - Statistics tracking (hits, misses, evictions, hit rate)
    - Pattern-based invalidation
    - Key generation helpers
    """

    def __init__(self, max_size: int = 1000, default_ttl: int | None = 10, enabled: bool = True):
        """
        Initialize the cache manager.

        Args:
            max_size: Maximum number of entries before LRU eviction
            default_ttl: Default time-to-live in seconds (None = no expiration)
            enabled: Whether caching is enabled (for testing/debugging)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enabled = enabled

        # OrderedDict preserves insertion order for LRU
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = Lock()

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key
            default: Default value if key not found or expired

        Returns:
            Cached value or default
        """
        if not self.enabled:
            return default

        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return default

            value, expiry_time = self._cache[key]

            # Check if expired
            if expiry_time is not None and time.time() > expiry_time:
                # Expired - remove and count as miss
                del self._cache[key]
                self._stats["misses"] += 1
                return default

            # Cache hit - move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (overrides default_ttl, None = no expiration)
        """
        if not self.enabled:
            return

        with self._lock:
            # Calculate expiry time
            if ttl is None:
                ttl = self.default_ttl

            expiry_time = None if ttl is None else time.time() + ttl

            # If key exists, update it (move to end)
            if key in self._cache:
                del self._cache[key]

            # Add new entry
            self._cache[key] = (value, expiry_time)

            # Enforce max size (evict oldest)
            if len(self._cache) > self.max_size:
                # Remove oldest (first item in OrderedDict)
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

    def has_key(self, key: str) -> bool:
        """
        Check if a key exists in the cache (not expired).

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        if not self.enabled:
            return False

        with self._lock:
            if key not in self._cache:
                return False

            value, expiry_time = self._cache[key]

            # Check if expired
            if expiry_time is not None and time.time() > expiry_time:
                del self._cache[key]
                return False

            return True

    def clear(self, reset_stats: bool = True) -> None:
        """
        Clear all cache entries.

        Args:
            reset_stats: If True, also reset hit/miss/eviction statistics
        """
        with self._lock:
            self._cache.clear()
            if reset_stats:
                self._stats = {
                    "hits": 0,
                    "misses": 0,
                    "evictions": 0,
                }

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache keys matching a pattern.

        Uses fnmatch for pattern matching (supports * and ? wildcards).

        Args:
            pattern: Pattern to match (e.g., "user:*:profile")

        Returns:
            Number of keys invalidated
        """
        with self._lock:
            keys_to_remove = [key for key in self._cache.keys() if fnmatch.fnmatch(key, pattern)]

            for key in keys_to_remove:
                del self._cache[key]

            return len(keys_to_remove)

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, evictions, size, and hit_rate
        """
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "size": len(self._cache),
                "hit_rate": hit_rate,
            }

    def reset_stats(self) -> None:
        """Reset statistics counters (cache contents remain)."""
        with self._lock:
            self._stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
            }

    def make_key(self, prefix: str, **kwargs) -> str:
        """
        Generate a consistent cache key from parameters.

        Args:
            prefix: Key prefix (e.g., function name)
            **kwargs: Parameters to include in key

        Returns:
            Cache key string
        """
        # Sort kwargs for consistent ordering
        sorted_params = sorted(kwargs.items())

        # Create a string representation
        params_str = json.dumps(sorted_params, sort_keys=True)

        # Hash for shorter keys with large parameters
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]

        return f"{prefix}:{params_hash}"


# Singleton instance for global use
_global_cache: CacheManager | None = None


def get_cache() -> CacheManager:
    """
    Get or create the global cache instance.

    Returns:
        Global CacheManager instance
    """
    global _global_cache
    if _global_cache is None:
        # Import config here to avoid circular imports
        from src.config import CACHE_ENABLED, CACHE_MAX_SIZE, HA_STATE_CACHE_TTL

        _global_cache = CacheManager(
            max_size=CACHE_MAX_SIZE,
            default_ttl=HA_STATE_CACHE_TTL,
            enabled=CACHE_ENABLED,
        )
    return _global_cache


def clear_global_cache() -> None:
    """Clear the global cache instance."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
