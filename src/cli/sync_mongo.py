"""
CronJob entry point: python -m src.cli.sync_mongo

Fetches full server data from all configured vendors and upserts
documents into MongoDB. Intended to run daily as a Kubernetes CronJob.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List

# Fix imports when run as a script
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "src.cli"

from ..config import (
    AppConfig,
    VendorConfig,
    load_environment,
    setup_logging,
    validate_sync_config,
)
from ..repositories.strategy_factory import StrategyFactory
from ..strategies.base_strategy import VendorStrategy, VendorType
from ..storage.database.mongo_client import MongoDatabase
from ..storage.database.server_repository import ServerRepository
from ..services.sync_service import SyncService


def build_strategies() -> List[VendorStrategy]:
    """Instantiate all configured vendor strategies."""
    credentials_map = {
        VendorType.HP: {
            "ip": VendorConfig.ONEVIEW_IP,
            "username": VendorConfig.ONEVIEW_USERNAME,
            "password": VendorConfig.ONEVIEW_PASSWORD,
        },
        VendorType.DELL: {
            "ip": VendorConfig.OME_IP,
            "username": VendorConfig.OME_USERNAME,
            "password": VendorConfig.OME_PASSWORD,
        },
        VendorType.CISCO: {
            "central_ip": VendorConfig.UCS_CENTRAL_IP,
            "central_username": VendorConfig.UCS_CENTRAL_USERNAME,
            "central_password": VendorConfig.UCS_CENTRAL_PASSWORD,
            "manager_username": VendorConfig.UCS_MANAGER_USERNAME,
            "manager_password": VendorConfig.UCS_MANAGER_PASSWORD,
        },
    }

    strategies = []
    for vendor_type, creds in credentials_map.items():
        strategy = StrategyFactory.create_strategy(vendor_type, creds)
        if strategy.is_configured():
            strategies.append(strategy)
            logging.getLogger(__name__).info(f"Using strategy: {vendor_type.value}")

    return strategies


async def main() -> int:
    """Run the sync and return exit code (0=success, 1=errors)."""
    logger = logging.getLogger(__name__)

    mongo_db = MongoDatabase(AppConfig.MONGO_URI, AppConfig.MONGO_DB_NAME, AppConfig.TLS_VERIFY)
    await mongo_db.connect()

    try:
        server_repo = ServerRepository(mongo_db)
        strategies = build_strategies()

        pattern = AppConfig.DEFAULT_ZONE_PATTERN
        sync_svc = SyncService(
            strategies,
            server_repo,
            pattern=pattern,
            batch_size=AppConfig.SYNC_BATCH_SIZE,
            batch_delay=AppConfig.SYNC_BATCH_DELAY,
        )

        result = await sync_svc.run_full_sync()

        if result.errors:
            logger.warning(f"Sync finished with {len(result.errors)} error(s)")
            for err in result.errors:
                logger.warning(f"  {err}")
            return 1

        logger.info(f"Sync succeeded: {result.n_upserted} servers upserted")
        return 0

    finally:
        await mongo_db.disconnect()


if __name__ == "__main__":
    load_environment()
    setup_logging()

    try:
        validate_sync_config()
    except ValueError as e:
        logging.getLogger(__name__).error(f"Configuration error: {e}")
        sys.exit(1)

    sys.exit(asyncio.run(main()))
