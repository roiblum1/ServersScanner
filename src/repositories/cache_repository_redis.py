"""
Redis-based cache repository for distributed caching across pods.

Stores expensive vendor API scan results in Redis for sharing between pods.
Maintenance data still uses PVC for persistence.
"""

from datetime import datetime, timedelta
import json
import logging
from typing import Dict, Optional
import redis.asyncio as redis
from ..models.api_responses import DashboardData

logger = logging.getLogger(__name__)


class CacheEntry:
    """
    Cache entry with timestamp and scanning state.

    Compatible with in-memory cache interface.
    """

    def __init__(self, data, timestamp: datetime):
        """
        Initialize cache entry.

        Args:
            data: Cached data (DashboardData)
            timestamp: When this entry was created
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


class RedisCacheRepository:
    """
    Redis-based distributed cache repository.

    Features:
    - Distributed caching across multiple pods
    - TTL-based expiration (handled by Redis)
    - Scan state management to prevent duplicate scans
    - Compatible with existing CacheRepository interface
    """

    def __init__(self, ttl_seconds: int, redis_host: str = "redis", redis_port: int = 6379, redis_db: int = 0):
        """
        Initialize Redis cache repository.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
        """
        self.ttl_seconds = ttl_seconds
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self._redis: Optional[redis.Redis] = None
        logger.debug(f"Initialized RedisCacheRepository with TTL={ttl_seconds}s, host={redis_host}:{redis_port}/{redis_db}")

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5
            )
            logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}/{self.redis_db}")
        return self._redis

    def _cache_key(self, key: str) -> str:
        """Generate Redis key with namespace."""
        return f"scanner:cache:{key}"

    def _scan_key(self, key: str) -> str:
        """Generate Redis key for scan state."""
        return f"scanner:scanning:{key}"

    def _timestamp_key(self, key: str) -> str:
        """Generate Redis key for timestamp."""
        return f"scanner:timestamp:{key}"

    async def get(self, key: str) -> Optional[CacheEntry]:
        """
        Get cached entry if exists and not expired.

        Args:
            key: Cache key

        Returns:
            CacheEntry if exists and not expired, None otherwise
        """
        try:
            r = await self._get_redis()
            cache_key = self._cache_key(key)
            timestamp_key = self._timestamp_key(key)

            # Get data and timestamp
            data_json = await r.get(cache_key)
            timestamp_str = await r.get(timestamp_key)

            if data_json and timestamp_str:
                # Deserialize data
                data_dict = json.loads(data_json)
                dashboard_data = DashboardData(**data_dict)

                # Parse timestamp
                timestamp = datetime.fromisoformat(timestamp_str.decode())

                entry = CacheEntry(dashboard_data, timestamp)

                # Check if expired
                if entry.is_expired(self.ttl_seconds):
                    logger.info(f"Redis cache EXPIRED for key '{key}' (age: {entry.age_seconds()}s)")
                    # Clean up expired entries
                    await r.delete(cache_key, timestamp_key)
                    return None

                logger.info(f"Redis cache HIT for key '{key}' (age: {entry.age_seconds()}s)")
                return entry
            else:
                logger.info(f"Redis cache MISS for key '{key}'")
                return None

        except redis.RedisError as e:
            logger.error(f"Redis error getting key '{key}': {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting cache key '{key}': {e}")
            return None

    async def set(self, key: str, data: DashboardData) -> None:
        """
        Store data in Redis cache with TTL.

        Args:
            key: Cache key
            data: DashboardData to cache
        """
        try:
            r = await self._get_redis()
            cache_key = self._cache_key(key)
            timestamp_key = self._timestamp_key(key)

            # Serialize data
            data_json = json.dumps(data.dict())
            timestamp = datetime.now()
            timestamp_str = timestamp.isoformat()

            # Store with TTL (add 60 seconds buffer for timestamp)
            await r.setex(cache_key, self.ttl_seconds + 60, data_json)
            await r.setex(timestamp_key, self.ttl_seconds + 60, timestamp_str)

            logger.info(f"Redis cache SET for key '{key}' with TTL={self.ttl_seconds}s")

        except redis.RedisError as e:
            logger.error(f"Redis error setting key '{key}': {e}")
        except Exception as e:
            logger.error(f"Error setting cache key '{key}': {e}")

    async def mark_scanning(self, key: str, scanning: bool) -> None:
        """
        Mark a cache entry as currently being scanned.

        Uses Redis key with short TTL to prevent stuck locks.

        Args:
            key: Cache key
            scanning: True to mark as scanning, False to clear
        """
        try:
            r = await self._get_redis()
            scan_key = self._scan_key(key)

            if scanning:
                # Set scanning flag with 10-minute TTL (auto-release if pod crashes)
                await r.setex(scan_key, 600, "1")
                logger.debug(f"Redis scan lock SET for key '{key}'")
            else:
                # Clear scanning flag
                await r.delete(scan_key)
                logger.debug(f"Redis scan lock RELEASED for key '{key}'")

        except redis.RedisError as e:
            logger.error(f"Redis error marking scanning for '{key}': {e}")
        except Exception as e:
            logger.error(f"Error marking scanning for '{key}': {e}")

    async def is_scanning(self, key: str) -> bool:
        """
        Check if a scan is in progress for this key.

        Args:
            key: Cache key

        Returns:
            True if scanning, False otherwise
        """
        try:
            r = await self._get_redis()
            scan_key = self._scan_key(key)
            result = await r.get(scan_key)
            return result is not None

        except redis.RedisError as e:
            logger.error(f"Redis error checking scanning for '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking scanning for '{key}': {e}")
            return False

    async def clear(self) -> None:
        """Clear all cache entries with scanner namespace."""
        try:
            r = await self._get_redis()

            # Find all keys with scanner namespace
            pattern = "scanner:*"
            keys = []
            async for key in r.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await r.delete(*keys)
                logger.info(f"Redis cache CLEARED ({len(keys)} keys deleted)")
            else:
                logger.info("Redis cache CLEARED (no keys found)")

        except redis.RedisError as e:
            logger.error(f"Redis error clearing cache: {e}")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def get_all_status(self) -> Dict[str, Dict]:
        """
        Get status of all cache entries (synchronous for compatibility).

        Note: This is a simplified version for Redis.
        For full status, use async get_all_status_async().

        Returns:
            Dictionary mapping cache keys to their status
        """
        # This is a compatibility method - in Redis we'd need to scan all keys
        # For now, return empty dict (status endpoint can call async version)
        logger.warning("get_all_status() called on Redis cache - use get_all_status_async() instead")
        return {}

    async def get_all_status_async(self) -> Dict[str, Dict]:
        """
        Get status of all cache entries (async version).

        Returns:
            Dictionary mapping cache keys to their status
        """
        try:
            r = await self._get_redis()
            status = {}

            # Find all cache keys
            pattern = self._cache_key("*")
            async for cache_key_bytes in r.scan_iter(match=pattern):
                cache_key = cache_key_bytes.decode()
                # Extract original key from namespaced key
                key = cache_key.replace("scanner:cache:", "")

                timestamp_key = self._timestamp_key(key)
                scan_key = self._scan_key(key)

                # Get timestamp
                timestamp_str = await r.get(timestamp_key)
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.decode())
                    age_secs = int((datetime.now() - timestamp).total_seconds())
                    expired = age_secs > self.ttl_seconds
                    next_refresh = max(0, self.ttl_seconds - age_secs)
                else:
                    age_secs = 0
                    expired = True
                    next_refresh = 0

                # Check if scanning
                is_scanning = await r.get(scan_key) is not None

                status[key] = {
                    "age_seconds": age_secs,
                    "expired": expired,
                    "is_scanning": is_scanning,
                    "next_refresh_seconds": next_refresh
                }

            return status

        except redis.RedisError as e:
            logger.error(f"Redis error getting status: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {}

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
            self._redis = None
