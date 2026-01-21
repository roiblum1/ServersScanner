"""
Cache repository for in-memory dashboard data caching.

Provides thread-safe caching with TTL and scan state management.
"""

from datetime import datetime, timedelta
import asyncio
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """
    Cache entry with timestamp and scanning state.

    Attributes:
        data: Cached data (any type)
        timestamp: When this entry was created
        is_scanning: Whether a scan is currently in progress for this entry
    """

    def __init__(self, data, timestamp: datetime):
        """
        Initialize cache entry.

        Args:
            data: Data to cache
            timestamp: Timestamp when data was cached
        """
        self.data = data
        self.timestamp = timestamp
        self.is_scanning = False

    def is_expired(self, ttl_seconds: int) -> bool:
        """
        Check if cache entry is older than TTL.

        Args:
            ttl_seconds: Time-to-live in seconds

        Returns:
            True if expired, False otherwise
        """
        return datetime.now() - self.timestamp > timedelta(seconds=ttl_seconds)

    def age_seconds(self) -> int:
        """
        Get age of cache in seconds.

        Returns:
            Age in seconds
        """
        return int((datetime.now() - self.timestamp).total_seconds())


class CacheRepository:
    """
    Thread-safe in-memory cache repository.

    Features:
    - TTL-based expiration
    - Scan state management to prevent duplicate scans
    - Async-safe with locks
    - Status introspection for monitoring
    """

    def __init__(self, ttl_seconds: int):
        """
        Initialize cache repository.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = asyncio.Lock()
        logger.debug(f"Initialized CacheRepository with TTL={ttl_seconds}s")

    async def get(self, key: str) -> Optional[CacheEntry]:
        """
        Get cached entry if exists and not expired.

        Args:
            key: Cache key

        Returns:
            CacheEntry if exists and not expired, None otherwise
        """
        async with self.lock:
            entry = self.cache.get(key)
            if entry and not entry.is_expired(self.ttl_seconds):
                logger.info(f"Cache HIT for key '{key}' (age: {entry.age_seconds()}s)")
                return entry
            elif entry:
                logger.info(f"Cache EXPIRED for key '{key}' (age: {entry.age_seconds()}s)")
            else:
                logger.info(f"Cache MISS for key '{key}'")
            return None

    async def set(self, key: str, data) -> None:
        """
        Store data in cache with current timestamp.

        Args:
            key: Cache key
            data: Data to cache
        """
        async with self.lock:
            self.cache[key] = CacheEntry(data, datetime.now())
            logger.info(f"Cache SET for key '{key}'")

    async def mark_scanning(self, key: str, scanning: bool) -> None:
        """
        Mark a cache entry as currently being scanned.

        Args:
            key: Cache key
            scanning: True to mark as scanning, False to clear
        """
        async with self.lock:
            entry = self.cache.get(key)
            if entry:
                entry.is_scanning = scanning
                logger.debug(f"Cache key '{key}' scanning={scanning}")

    async def is_scanning(self, key: str) -> bool:
        """
        Check if a scan is in progress for this key.

        Args:
            key: Cache key

        Returns:
            True if scanning, False otherwise
        """
        async with self.lock:
            entry = self.cache.get(key)
            return entry.is_scanning if entry else False

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self.lock:
            self.cache.clear()
            logger.info("Cache CLEARED")

    def get_all_status(self) -> Dict[str, Dict]:
        """
        Get status of all cache entries (non-async for introspection).

        Returns:
            Dictionary mapping cache keys to their status
        """
        status = {}
        for key, entry in self.cache.items():
            status[key] = {
                "age_seconds": entry.age_seconds(),
                "expired": entry.is_expired(self.ttl_seconds),
                "is_scanning": entry.is_scanning,
                "next_refresh_seconds": max(0, self.ttl_seconds - entry.age_seconds())
            }
        return status
