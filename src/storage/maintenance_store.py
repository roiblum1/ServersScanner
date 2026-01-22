"""
Maintenance store for persistent server maintenance records.

Thread-safe storage with file locking for multi-pod environments.
"""

import os
import json
import fcntl
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MaintenanceRecord(BaseModel):
    """Maintenance record for a server"""
    reason: str
    severity: str  # "critical" | "high" | "medium" | "low"
    timestamp: str
    created_by: Optional[str] = None


class MaintenanceStore:
    """
    Thread-safe persistent storage for server maintenance records.

    Uses file locking (fcntl) for multi-pod safety and atomic writes
    for consistency.
    """

    def __init__(self, data_dir: Path = Path("/app/data")):
        """
        Initialize maintenance store.

        Args:
            data_dir: Directory to store maintenance.json
        """
        self.data_dir = data_dir
        self.file_path = data_dir / "maintenance.json"
        self._initialized = False

    async def initialize(self):
        """
        Initialize storage directory and file.
        Creates directory and empty JSON file if they don't exist.
        """
        try:
            # Create directory if it doesn't exist
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Create empty file if it doesn't exist
            if not self.file_path.exists():
                initial_data = {
                    "version": "1.0",
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "servers": {}
                }
                await self._write_file(initial_data)
                logger.info(f"Initialized maintenance store at {self.file_path}")
            else:
                logger.info(f"Maintenance store exists at {self.file_path}")

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize maintenance store: {e}")
            # Degrade gracefully - feature will be disabled but app continues
            self._initialized = False

    def _normalize_name(self, server_name: str) -> str:
        """Normalize server name for case-insensitive storage"""
        return server_name.lower().strip()

    async def _read_file(self) -> dict:
        """
        Read maintenance.json with file locking.

        Returns:
            Dictionary with maintenance data
        """
        if not self._initialized:
            logger.warning("Maintenance store not initialized, returning empty data")
            return {"version": "1.0", "last_updated": "", "servers": {}}

        try:
            with open(self.file_path, 'r') as f:
                # Acquire shared lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    return data
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        except FileNotFoundError:
            logger.warning(f"Maintenance file not found: {self.file_path}")
            return {"version": "1.0", "last_updated": "", "servers": {}}

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in maintenance file: {e}")
            return {"version": "1.0", "last_updated": "", "servers": {}}

        except Exception as e:
            logger.error(f"Error reading maintenance file: {e}")
            return {"version": "1.0", "last_updated": "", "servers": {}}

    async def _write_file(self, data: dict):
        """
        Write maintenance.json atomically with file locking.

        Uses temp file + rename for atomic writes.

        Args:
            data: Complete maintenance data to write
        """
        if not self._initialized:
            logger.warning("Maintenance store not initialized, skipping write")
            return

        temp_path = self.file_path.with_suffix('.json.tmp')

        try:
            # Update last_updated timestamp
            data["last_updated"] = datetime.utcnow().isoformat() + "Z"

            # Write to temp file with exclusive lock
            with open(temp_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            temp_path.rename(self.file_path)
            logger.debug(f"Wrote maintenance data to {self.file_path}")

        except Exception as e:
            logger.error(f"Error writing maintenance file: {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            raise

    async def get_maintenance(self, server_name: str) -> Optional[MaintenanceRecord]:
        """
        Get maintenance record for a specific server.

        Args:
            server_name: Server profile name (case-insensitive)

        Returns:
            MaintenanceRecord if found, None otherwise
        """
        normalized = self._normalize_name(server_name)
        data = await self._read_file()

        servers = data.get("servers", {})
        record_data = servers.get(normalized)

        if record_data:
            try:
                return MaintenanceRecord(**record_data)
            except Exception as e:
                logger.error(f"Invalid maintenance record for {server_name}: {e}")
                return None

        return None

    async def set_maintenance(self, server_name: str, record: MaintenanceRecord):
        """
        Set or update maintenance record for a server.

        Args:
            server_name: Server profile name (case-insensitive)
            record: Maintenance record to store
        """
        normalized = self._normalize_name(server_name)
        data = await self._read_file()

        # Ensure servers dict exists
        if "servers" not in data:
            data["servers"] = {}

        # Store record
        data["servers"][normalized] = record.dict()

        await self._write_file(data)
        logger.info(f"Set maintenance for {server_name}: {record.severity} - {record.reason[:50]}")

    async def remove_maintenance(self, server_name: str):
        """
        Remove maintenance record for a server.

        Args:
            server_name: Server profile name (case-insensitive)
        """
        normalized = self._normalize_name(server_name)
        data = await self._read_file()

        servers = data.get("servers", {})
        if normalized in servers:
            del servers[normalized]
            data["servers"] = servers
            await self._write_file(data)
            logger.info(f"Removed maintenance for {server_name}")
        else:
            logger.debug(f"No maintenance record found for {server_name}")

    async def get_all_maintenance(self) -> Dict[str, MaintenanceRecord]:
        """
        Get all maintenance records.

        Returns:
            Dictionary mapping normalized server names to MaintenanceRecord objects
        """
        data = await self._read_file()
        servers = data.get("servers", {})

        result = {}
        for server_name, record_data in servers.items():
            try:
                result[server_name] = MaintenanceRecord(**record_data)
            except Exception as e:
                logger.error(f"Invalid maintenance record for {server_name}: {e}")
                continue

        return result

    async def clear_all(self):
        """Clear all maintenance records (for testing)"""
        data = {
            "version": "1.0",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "servers": {}
        }
        await self._write_file(data)
        logger.info("Cleared all maintenance records")
