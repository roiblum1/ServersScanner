"""
Maintenance repository for business logic wrapper around MaintenanceStore.

Provides a cleaner interface for maintenance operations with automatic
conversion between storage and API models.
"""

from typing import Optional, Dict
import logging
from ..storage import MaintenanceStore, MaintenanceRecord
from ..models.api_responses import MaintenanceInfo

logger = logging.getLogger(__name__)


class MaintenanceRepository:
    """
    Repository for maintenance data with business logic wrapper.

    Bridges MaintenanceStore (persistence) and API models (presentation).
    """

    def __init__(self, store: MaintenanceStore):
        """
        Initialize maintenance repository.

        Args:
            store: MaintenanceStore instance for persistence
        """
        self.store = store

    async def get(self, server_name: str) -> Optional[MaintenanceInfo]:
        """
        Get maintenance record for server.

        Args:
            server_name: Server profile name (case-insensitive)

        Returns:
            MaintenanceInfo if found, None otherwise
        """
        record = await self.store.get_maintenance(server_name)
        if record:
            return MaintenanceInfo(**record.dict())
        return None

    async def set(self, server_name: str, maintenance: MaintenanceInfo) -> None:
        """
        Set maintenance record for server.

        Args:
            server_name: Server profile name (case-insensitive)
            maintenance: Maintenance information to store
        """
        record = MaintenanceRecord(**maintenance.dict())
        await self.store.set_maintenance(server_name, record)
        logger.info(f"Set maintenance for {server_name}: {maintenance.severity}")

    async def remove(self, server_name: str) -> None:
        """
        Remove maintenance record.

        Args:
            server_name: Server profile name (case-insensitive)
        """
        await self.store.remove_maintenance(server_name)
        logger.info(f"Removed maintenance for {server_name}")

    async def get_all(self) -> Dict[str, MaintenanceInfo]:
        """
        Get all maintenance records.

        Returns:
            Dictionary mapping normalized server names to MaintenanceInfo objects
        """
        records = await self.store.get_all_maintenance()
        return {
            name: MaintenanceInfo(**record.dict())
            for name, record in records.items()
        }

    async def clear_all(self) -> None:
        """Clear all maintenance records (for testing)."""
        await self.store.clear_all()
        logger.info("Cleared all maintenance records")
