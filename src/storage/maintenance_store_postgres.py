"""
PostgreSQL-based maintenance store for persistent server maintenance records.

Replaces file-based storage with PostgreSQL for better reliability,
scalability, and concurrent access.
"""

import logging
from typing import Optional, Dict
from datetime import datetime
import asyncpg
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MaintenanceRecord(BaseModel):
    """Maintenance record for a server"""
    reason: str
    severity: str  # "critical" | "high" | "medium" | "low"
    timestamp: str
    created_by: Optional[str] = None


class MaintenanceStorePostgres:
    """
    PostgreSQL-based persistent storage for server maintenance records.

    Uses asyncpg for async PostgreSQL access with connection pooling.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "server_scanner",
        user: str = "scanner",
        password: str = "scanner",
        min_pool_size: int = 5,
        max_pool_size: int = 20
    ):
        """
        Initialize PostgreSQL maintenance store.

        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
            min_pool_size: Minimum connection pool size
            max_pool_size: Maximum connection pool size
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self):
        """
        Initialize database connection pool and create tables.
        """
        try:
            # Create connection pool
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_pool_size,
                max_size=self.max_pool_size,
                command_timeout=60
            )

            # Create table if not exists
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS server_maintenance (
                        server_name VARCHAR(255) PRIMARY KEY,
                        reason TEXT NOT NULL,
                        severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        created_by VARCHAR(255),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create index for faster queries
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_maintenance_severity
                    ON server_maintenance(severity)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_maintenance_timestamp
                    ON server_maintenance(timestamp)
                """)

            self._initialized = True
            logger.info(f"PostgreSQL maintenance store initialized: {self.host}:{self.port}/{self.database}")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL maintenance store: {e}")
            self._initialized = False
            raise

    async def close(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL connection pool closed")

    def _normalize_name(self, server_name: str) -> str:
        """Normalize server name for case-insensitive storage"""
        return server_name.lower().strip()

    async def get_maintenance(self, server_name: str) -> Optional[MaintenanceRecord]:
        """
        Get maintenance record for a specific server.

        Args:
            server_name: Server profile name (case-insensitive)

        Returns:
            MaintenanceRecord if found, None otherwise
        """
        if not self._initialized:
            logger.warning("Maintenance store not initialized, returning None")
            return None

        normalized = self._normalize_name(server_name)

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT reason, severity, timestamp, created_by
                    FROM server_maintenance
                    WHERE server_name = $1
                    """,
                    normalized
                )

                if row:
                    return MaintenanceRecord(
                        reason=row['reason'],
                        severity=row['severity'],
                        timestamp=row['timestamp'].isoformat() + 'Z',
                        created_by=row['created_by']
                    )

                return None

        except Exception as e:
            logger.error(f"Error getting maintenance for {server_name}: {e}")
            return None

    async def set_maintenance(self, server_name: str, record: MaintenanceRecord):
        """
        Set or update maintenance record for a server.

        Args:
            server_name: Server profile name (case-insensitive)
            record: Maintenance record to store
        """
        if not self._initialized:
            logger.warning("Maintenance store not initialized, skipping write")
            return

        normalized = self._normalize_name(server_name)

        try:
            # Parse timestamp
            timestamp = datetime.fromisoformat(record.timestamp.replace('Z', '+00:00'))

            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO server_maintenance (server_name, reason, severity, timestamp, created_by, updated_at)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                    ON CONFLICT (server_name)
                    DO UPDATE SET
                        reason = EXCLUDED.reason,
                        severity = EXCLUDED.severity,
                        timestamp = EXCLUDED.timestamp,
                        created_by = EXCLUDED.created_by,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    normalized,
                    record.reason,
                    record.severity,
                    timestamp,
                    record.created_by
                )

            logger.info(f"Set maintenance for {server_name}: {record.severity} - {record.reason[:50]}")

        except Exception as e:
            logger.error(f"Error setting maintenance for {server_name}: {e}")
            raise

    async def remove_maintenance(self, server_name: str):
        """
        Remove maintenance record for a server.

        Args:
            server_name: Server profile name (case-insensitive)
        """
        if not self._initialized:
            logger.warning("Maintenance store not initialized, skipping delete")
            return

        normalized = self._normalize_name(server_name)

        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM server_maintenance
                    WHERE server_name = $1
                    """,
                    normalized
                )

                if result == "DELETE 1":
                    logger.info(f"Removed maintenance for {server_name}")
                else:
                    logger.debug(f"No maintenance record found for {server_name}")

        except Exception as e:
            logger.error(f"Error removing maintenance for {server_name}: {e}")
            raise

    async def get_all_maintenance(self) -> Dict[str, MaintenanceRecord]:
        """
        Get all maintenance records.

        Returns:
            Dictionary mapping normalized server names to MaintenanceRecord objects
        """
        if not self._initialized:
            logger.warning("Maintenance store not initialized, returning empty dict")
            return {}

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT server_name, reason, severity, timestamp, created_by
                    FROM server_maintenance
                    ORDER BY timestamp DESC
                    """
                )

                result = {}
                for row in rows:
                    result[row['server_name']] = MaintenanceRecord(
                        reason=row['reason'],
                        severity=row['severity'],
                        timestamp=row['timestamp'].isoformat() + 'Z',
                        created_by=row['created_by']
                    )

                return result

        except Exception as e:
            logger.error(f"Error getting all maintenance records: {e}")
            return {}

    async def clear_all(self):
        """Clear all maintenance records (for testing)"""
        if not self._initialized:
            logger.warning("Maintenance store not initialized, skipping clear")
            return

        try:
            async with self._pool.acquire() as conn:
                await conn.execute("DELETE FROM server_maintenance")

            logger.info("Cleared all maintenance records")

        except Exception as e:
            logger.error(f"Error clearing maintenance records: {e}")
            raise

    async def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about maintenance records.

        Returns:
            Dictionary with counts by severity
        """
        if not self._initialized:
            return {}

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT severity, COUNT(*) as count
                    FROM server_maintenance
                    GROUP BY severity
                    """
                )

                stats = {row['severity']: row['count'] for row in rows}
                return stats

        except Exception as e:
            logger.error(f"Error getting maintenance stats: {e}")
            return {}
