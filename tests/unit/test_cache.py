"""
Cache Module Tests

Test Strategy:
- Test basic cache set/get operations
- Test TTL expiry (time-based eviction)
- Test max size eviction (LRU-style)
- Test cache statistics tracking (hits, misses, evictions)
- Test cache invalidation (clear, clear_pattern)
- Test thread safety if needed

Mocking Strategy:
- Mock time.time() for TTL testing
- Integration test actual cache behavior
- No external dependencies to mock
"""

import time
from unittest.mock import patch

import pytest


def test_cache_set_and_get():
    """Test basic cache set and get operations."""
    from src.cache import CacheManager

    cache = CacheManager()

    # Set a value
    cache.set("test_key", "test_value")

    # Get the value
    value = cache.get("test_key")
    assert value == "test_value"

    # Get a non-existent key
    value = cache.get("nonexistent")
    assert value is None


def test_cache_get_with_default():
    """Test cache get with default value."""
    from src.cache import CacheManager

    cache = CacheManager()

    # Get non-existent key with default
    value = cache.get("missing", default="default_value")
    assert value == "default_value"

    # Set and get should override default
    cache.set("existing", "real_value")
    value = cache.get("existing", default="default_value")
    assert value == "real_value"


def test_cache_ttl_expiry():
    """Test that cache entries expire after TTL."""
    from src.cache import CacheManager

    cache = CacheManager(default_ttl=2)  # 2 second TTL

    # Mock time for consistent testing
    with patch("time.time") as mock_time:
        start_time = 1000.0
        mock_time.return_value = start_time

        # Set a value at time 1000
        with patch("src.cache.time.time", return_value=start_time):
            cache.set("test_key", "test_value")

        # 1 second later - should still be valid
        with patch("src.cache.time.time", return_value=start_time + 1):
            assert cache.get("test_key") == "test_value"

        # 3 seconds later - should be expired (TTL was 2 seconds)
        with patch("src.cache.time.time", return_value=start_time + 3):
            assert cache.get("test_key") is None


def test_cache_custom_ttl():
    """Test that individual entries can have custom TTLs."""
    from src.cache import CacheManager

    cache = CacheManager(default_ttl=10)  # 10 second default

    # Mock time passing
    start_time = 2000.0

    # Set with custom TTL at time 2000
    with patch("src.cache.time.time", return_value=start_time):
        cache.set("short_lived", "value1", ttl=1)
        cache.set("long_lived", "value2", ttl=20)

    # After 2 seconds, short_lived should be gone but long_lived remains
    with patch("src.cache.time.time", return_value=start_time + 2):
        assert cache.get("short_lived") is None
        assert cache.get("long_lived") == "value2"


def test_cache_max_size_eviction():
    """Test that cache evicts oldest entries when max_size is reached."""
    from src.cache import CacheManager

    # Create cache with max size of 3
    cache = CacheManager(max_size=3, default_ttl=None)  # No TTL, only size limit

    # Add 3 entries
    cache.set("key1", "value1")
    time.sleep(0.01)  # Small delay to ensure order
    cache.set("key2", "value2")
    time.sleep(0.01)
    cache.set("key3", "value3")

    # All 3 should be present
    assert cache.get("key1") == "value1"
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"

    # Add a 4th entry - should evict oldest (key1)
    time.sleep(0.01)
    cache.set("key4", "value4")

    # key1 should be evicted, others should remain
    assert cache.get("key1") is None
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"
    assert cache.get("key4") == "value4"


def test_cache_lru_access_updates():
    """Test that accessing an entry updates its position (LRU behavior)."""
    from src.cache import CacheManager

    cache = CacheManager(max_size=3, default_ttl=None)

    # Add 3 entries
    cache.set("key1", "value1")
    time.sleep(0.01)
    cache.set("key2", "value2")
    time.sleep(0.01)
    cache.set("key3", "value3")

    # Access key1 to make it recently used
    time.sleep(0.01)
    cache.get("key1")

    # Add key4 - should evict key2 (oldest unaccessed) instead of key1
    time.sleep(0.01)
    cache.set("key4", "value4")

    # key1 should still be present because we accessed it
    assert cache.get("key1") == "value1"
    # key2 should be evicted
    assert cache.get("key2") is None
    assert cache.get("key3") == "value3"
    assert cache.get("key4") == "value4"


def test_cache_statistics_tracking():
    """Test that cache tracks hits, misses, and evictions."""
    from src.cache import CacheManager

    cache = CacheManager(max_size=2, default_ttl=None)

    # Initial stats should be zero
    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["evictions"] == 0
    assert stats["size"] == 0

    # Set two values
    cache.set("key1", "value1")
    cache.set("key2", "value2")

    stats = cache.get_stats()
    assert stats["size"] == 2

    # Get existing key - should be a hit
    cache.get("key1")
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0

    # Get non-existent key - should be a miss
    cache.get("nonexistent")
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1

    # Add third value to trigger eviction
    cache.set("key3", "value3")
    stats = cache.get_stats()
    assert stats["evictions"] == 1
    assert stats["size"] == 2


def test_cache_hit_rate_calculation():
    """Test that cache calculates hit rate correctly."""
    from src.cache import CacheManager

    cache = CacheManager()

    cache.set("key1", "value1")

    # 3 hits, 1 miss = 75% hit rate
    cache.get("key1")  # hit
    cache.get("key1")  # hit
    cache.get("key1")  # hit
    cache.get("key2")  # miss

    stats = cache.get_stats()
    assert stats["hits"] == 3
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.75

    # Zero requests should give 0.0 hit rate
    cache2 = CacheManager()
    stats2 = cache2.get_stats()
    assert stats2["hit_rate"] == 0.0


def test_cache_clear():
    """Test that clear() removes all entries."""
    from src.cache import CacheManager

    cache = CacheManager()

    # Add multiple entries
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    # Verify they exist
    assert cache.get("key1") == "value1"
    stats = cache.get_stats()
    assert stats["size"] == 3

    # Clear cache
    cache.clear()

    # All entries should be gone
    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert cache.get("key3") is None

    stats = cache.get_stats()
    assert stats["size"] == 0


def test_cache_invalidate_pattern():
    """Test pattern-based cache invalidation."""
    from src.cache import CacheManager

    cache = CacheManager()

    # Add entries with different patterns
    cache.set("user:1:profile", "user1_data")
    cache.set("user:2:profile", "user2_data")
    cache.set("user:1:posts", "user1_posts")
    cache.set("session:abc123", "session_data")

    # Invalidate all user:1:* entries
    cache.invalidate_pattern("user:1:*")

    # user:1 entries should be gone
    assert cache.get("user:1:profile") is None
    assert cache.get("user:1:posts") is None

    # Other entries should remain
    assert cache.get("user:2:profile") == "user2_data"
    assert cache.get("session:abc123") == "session_data"


def test_cache_key_generation():
    """Test generating consistent cache keys from parameters."""
    from src.cache import CacheManager

    cache = CacheManager()

    # Test key generation helper
    key1 = cache.make_key("get_state", entity_id="light.living_room")
    key2 = cache.make_key("get_state", entity_id="light.living_room")
    key3 = cache.make_key("get_state", entity_id="light.bedroom")

    # Same parameters should generate same key
    assert key1 == key2

    # Different parameters should generate different keys
    assert key1 != key3


def test_cache_disable_flag():
    """Test that cache can be disabled via configuration."""
    from src.cache import CacheManager

    # Cache disabled
    cache = CacheManager(enabled=False)

    # Set should be no-op
    cache.set("key1", "value1")

    # Get should always return None
    assert cache.get("key1") is None

    # Stats should still work
    stats = cache.get_stats()
    assert stats["size"] == 0


def test_cache_reset_stats():
    """Test resetting cache statistics."""
    from src.cache import CacheManager

    cache = CacheManager()

    # Generate some stats
    cache.set("key1", "value1")
    cache.get("key1")  # hit
    cache.get("key2")  # miss

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1

    # Reset stats
    cache.reset_stats()

    # Stats should be zero but cache contents remain
    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert cache.get("key1") == "value1"  # Entry still exists


def test_cache_with_none_values():
    """Test that None can be cached as a value."""
    from src.cache import CacheManager

    cache = CacheManager()

    # Cache None value explicitly
    cache.set("null_key", None)

    # Should distinguish between cached None and missing key
    # Use has_key to check existence
    assert cache.has_key("null_key") is True
    assert cache.has_key("missing_key") is False

    # Get should return None for both but stats should differ
    initial_misses = cache.get_stats()["misses"]

    result1 = cache.get("null_key")
    assert result1 is None
    assert cache.get_stats()["misses"] == initial_misses  # Hit, not miss

    result2 = cache.get("missing_key")
    assert result2 is None
    assert cache.get_stats()["misses"] == initial_misses + 1  # Miss
