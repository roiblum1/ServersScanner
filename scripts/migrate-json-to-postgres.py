#!/usr/bin/env python3
"""
Database Migration Script: JSON to PostgreSQL

Migrates maintenance data from file-based JSON storage to PostgreSQL.

Usage:
    # From JSON file to PostgreSQL
    python migrate-json-to-postgres.py --json-file /path/to/maintenance.json

    # From Kubernetes PVC to PostgreSQL
    python migrate-json-to-postgres.py --from-k8s --namespace server-scanner --pvc-name scanner-data

    # Dry run (no actual migration)
    python migrate-json-to-postgres.py --json-file maintenance.json --dry-run

Environment Variables:
    POSTGRES_HOST       - PostgreSQL host (default: localhost)
    POSTGRES_PORT       - PostgreSQL port (default: 5432)
    POSTGRES_DB         - Database name (default: server_scanner)
    POSTGRES_USER       - Database user (required)
    POSTGRES_PASSWORD   - Database password (required)
"""

import asyncio
import argparse
import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationConfig:
    """Configuration for database migration"""

    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = os.getenv("POSTGRES_DB", "server_scanner")
        self.user = os.getenv("POSTGRES_USER")
        self.password = os.getenv("POSTGRES_PASSWORD")

        if not self.user or not self.password:
            raise ValueError(
                "POSTGRES_USER and POSTGRES_PASSWORD environment variables are required"
            )

    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class MaintenanceMigrator:
    """Migrates maintenance data from JSON to PostgreSQL"""

    def __init__(self, config: MigrationConfig, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.conn: Optional[asyncpg.Connection] = None

    async def connect(self):
        """Connect to PostgreSQL"""
        logger.info(f"Connecting to PostgreSQL at {self.config.host}:{self.config.port}")
        try:
            self.conn = await asyncpg.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password
            )
            logger.info("Successfully connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def disconnect(self):
        """Disconnect from PostgreSQL"""
        if self.conn:
            await self.conn.close()
            logger.info("Disconnected from PostgreSQL")

    async def verify_table_exists(self) -> bool:
        """Verify that server_maintenance table exists"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'server_maintenance'
            );
        """
        result = await self.conn.fetchval(query)
        return result

    async def create_table(self):
        """Create server_maintenance table if it doesn't exist"""
        logger.info("Creating server_maintenance table...")

        query = """
            CREATE TABLE IF NOT EXISTS server_maintenance (
                server_name VARCHAR(255) PRIMARY KEY,
                reason TEXT NOT NULL,
                severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                created_by VARCHAR(255),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """

        if not self.dry_run:
            await self.conn.execute(query)
            logger.info("Table created successfully")
        else:
            logger.info("[DRY RUN] Would create table")

        # Create indexes
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_server_maintenance_severity ON server_maintenance(severity);",
            "CREATE INDEX IF NOT EXISTS idx_server_maintenance_timestamp ON server_maintenance(timestamp);"
        ]

        for index_query in index_queries:
            if not self.dry_run:
                await self.conn.execute(index_query)
            else:
                logger.info(f"[DRY RUN] Would create index")

    async def get_existing_count(self) -> int:
        """Get count of existing records in database"""
        query = "SELECT COUNT(*) FROM server_maintenance;"
        count = await self.conn.fetchval(query)
        return count

    async def migrate_record(self, server_name: str, data: Dict[str, Any]) -> bool:
        """
        Migrate a single maintenance record.

        Returns True if successful, False otherwise.
        """
        try:
            # Normalize server name
            normalized_name = server_name.lower().strip()

            # Extract fields
            reason = data.get("reason", "")
            severity = data.get("severity", "medium")
            timestamp_str = data.get("timestamp", "")
            created_by = data.get("created_by")

            # Parse timestamp
            try:
                # Try ISO format first
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Fallback to current time
                logger.warning(f"Invalid timestamp for {server_name}, using current time")
                timestamp = datetime.now()

            # Validate severity
            if severity not in ["critical", "high", "medium", "low"]:
                logger.warning(f"Invalid severity '{severity}' for {server_name}, defaulting to 'medium'")
                severity = "medium"

            # Insert or update record
            query = """
                INSERT INTO server_maintenance (server_name, reason, severity, timestamp, created_by, updated_at)
                VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                ON CONFLICT (server_name)
                DO UPDATE SET
                    reason = EXCLUDED.reason,
                    severity = EXCLUDED.severity,
                    timestamp = EXCLUDED.timestamp,
                    created_by = EXCLUDED.created_by,
                    updated_at = CURRENT_TIMESTAMP;
            """

            if not self.dry_run:
                await self.conn.execute(query, normalized_name, reason, severity, timestamp, created_by)
                logger.info(f"✓ Migrated: {server_name}")
            else:
                logger.info(f"[DRY RUN] Would migrate: {server_name} (severity: {severity})")

            return True

        except Exception as e:
            logger.error(f"✗ Failed to migrate {server_name}: {e}")
            return False

    async def migrate_from_json(self, json_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Migrate all records from JSON data.

        Returns:
            Dict with 'total', 'success', 'failed' counts
        """
        stats = {"total": 0, "success": 0, "failed": 0}

        for server_name, data in json_data.items():
            stats["total"] += 1

            if await self.migrate_record(server_name, data):
                stats["success"] += 1
            else:
                stats["failed"] += 1

        return stats


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load maintenance data from JSON file"""
    logger.info(f"Loading JSON file: {file_path}")

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} records from JSON")
        return data
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        sys.exit(1)


def load_from_kubernetes(namespace: str, pvc_name: str, file_name: str = "maintenance.json") -> Dict[str, Any]:
    """Load JSON file from Kubernetes PVC using kubectl"""
    import subprocess

    logger.info(f"Loading from Kubernetes PVC: {namespace}/{pvc_name}")

    try:
        # Find pod using the PVC
        cmd = [
            "kubectl", "get", "pods",
            "-n", namespace,
            "-o", "json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        pods_data = json.loads(result.stdout)

        # Find pod with matching PVC
        pod_name = None
        for pod in pods_data.get("items", []):
            for volume in pod.get("spec", {}).get("volumes", []):
                pvc = volume.get("persistentVolumeClaim", {})
                if pvc.get("claimName") == pvc_name:
                    pod_name = pod["metadata"]["name"]
                    break
            if pod_name:
                break

        if not pod_name:
            logger.error(f"No pod found using PVC {pvc_name}")
            sys.exit(1)

        logger.info(f"Found pod: {pod_name}")

        # Copy file from pod
        temp_file = f"/tmp/maintenance-{namespace}.json"
        cmd = [
            "kubectl", "cp",
            f"{namespace}/{pod_name}:/app/data/{file_name}",
            temp_file
        ]
        subprocess.run(cmd, check=True)

        # Load the file
        data = load_json_file(temp_file)

        # Clean up
        os.remove(temp_file)

        return data

    except subprocess.CalledProcessError as e:
        logger.error(f"kubectl command failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load from Kubernetes: {e}")
        sys.exit(1)


async def main():
    parser = argparse.ArgumentParser(
        description="Migrate maintenance data from JSON to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--json-file",
        help="Path to JSON file to migrate"
    )

    parser.add_argument(
        "--from-k8s",
        action="store_true",
        help="Load JSON from Kubernetes PVC"
    )

    parser.add_argument(
        "--namespace",
        default="server-scanner",
        help="Kubernetes namespace (default: server-scanner)"
    )

    parser.add_argument(
        "--pvc-name",
        default="scanner-data",
        help="PVC name (default: scanner-data)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without actually migrating data"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load JSON data
    if args.from_k8s:
        json_data = load_from_kubernetes(args.namespace, args.pvc_name)
    elif args.json_file:
        json_data = load_json_file(args.json_file)
    else:
        parser.error("Either --json-file or --from-k8s must be specified")

    if not json_data:
        logger.warning("No data to migrate")
        return

    # Initialize migrator
    try:
        config = MigrationConfig()
        migrator = MaintenanceMigrator(config, dry_run=args.dry_run)

        await migrator.connect()

        # Verify/create table
        table_exists = await migrator.verify_table_exists()
        if not table_exists:
            logger.warning("Table server_maintenance does not exist")
            await migrator.create_table()
        else:
            logger.info("Table server_maintenance exists")

        # Get existing count
        existing_count = await migrator.get_existing_count()
        logger.info(f"Existing records in database: {existing_count}")

        # Perform migration
        logger.info("Starting migration...")
        stats = await migrator.migrate_from_json(json_data)

        # Print summary
        logger.info("=" * 60)
        logger.info("Migration Summary:")
        logger.info(f"  Total records:     {stats['total']}")
        logger.info(f"  Successfully migrated: {stats['success']}")
        logger.info(f"  Failed:            {stats['failed']}")

        if args.dry_run:
            logger.info("  (DRY RUN - no actual changes made)")

        logger.info("=" * 60)

        # Verify final count
        if not args.dry_run:
            final_count = await migrator.get_existing_count()
            logger.info(f"Final record count: {final_count}")

        await migrator.disconnect()

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
