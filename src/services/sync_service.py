"""
Sync service — CronJob orchestrator for MongoDB population.

Iterates over all configured vendor strategies, fetches full server
hardware details, and upserts documents into MongoDB.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List

UPSERT_MAX_RETRIES = 3

from ..strategies.base_strategy import VendorStrategy
from ..storage.database.server_repository import ServerRepository

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    n_upserted: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class SyncService:
    """
    Orchestrates daily vendor → MongoDB sync.

    Vendor API calls are blocking (sync), so each strategy is run in a
    thread pool via asyncio.to_thread to keep the event loop free for
    MongoDB writes.
    """

    def __init__(
        self,
        strategies: List[VendorStrategy],
        server_repo: ServerRepository,
        pattern: str = r"^(?:ocp4-hypershift|ocp)-.*",
        batch_size: int = 50,
        batch_delay: float = 1.0,
    ):
        self.strategies = strategies
        self.server_repo = server_repo
        self.pattern = pattern
        self.batch_size = batch_size
        self.batch_delay = batch_delay

    async def run_full_sync(self) -> SyncResult:
        """
        Run a full sync cycle:
        1. For each vendor strategy, fetch all matching server documents
        2. Upsert each document into MongoDB (preserving maintenance field)
        """
        result = SyncResult()
        # Track server_name → vendor for duplicate detection across vendors
        seen: dict[str, str] = {}

        logger.info(
            f"Starting sync: pattern='{self.pattern}', "
            f"batch_size={self.batch_size}, batch_delay={self.batch_delay}s"
        )

        for strategy in self.strategies:
            vendor = strategy.vendor_name
            logger.info(f"[{vendor}] Starting fetch...")
            try:
                # Blocking vendor API call — run in thread pool
                docs = await asyncio.to_thread(
                    strategy.get_full_server_data,
                    self.pattern,
                    True,               # hardware_details always True
                    self.batch_size,
                    self.batch_delay,
                )
                logger.info(f"[{vendor}] Fetched {len(docs)} servers → upserting to MongoDB")

                for doc in docs:
                    for attempt in range(1, UPSERT_MAX_RETRIES + 1):
                        try:
                            await self.server_repo.upsert_server(doc)
                            result.n_upserted += 1
                            # Duplicate detection: same name from a different vendor
                            if doc.id in seen:
                                conflicting_vendors = [seen[doc.id], vendor]
                                logger.warning(
                                    f"[{vendor}] '{doc.id}' also returned by "
                                    f"'{seen[doc.id]}' — flagging as conflict"
                                )
                                await self.server_repo.set_conflict(doc.id, conflicting_vendors)
                            else:
                                seen[doc.id] = vendor
                            break
                        except Exception as e:
                            if attempt < UPSERT_MAX_RETRIES:
                                wait = 2 ** (attempt - 1)
                                logger.warning(
                                    f"[{vendor}] Upsert attempt {attempt}/{UPSERT_MAX_RETRIES} "
                                    f"failed for '{doc.id}', retrying in {wait}s: {e}"
                                )
                                await asyncio.sleep(wait)
                            else:
                                msg = f"[{vendor}] Failed to upsert '{doc.id}' after {UPSERT_MAX_RETRIES} attempts: {e}"
                                logger.error(msg)
                                result.errors.append(msg)

            except Exception as e:
                msg = f"[{vendor}] Strategy error: {e}"
                logger.error(msg, exc_info=True)
                result.errors.append(msg)
            finally:
                try:
                    await asyncio.to_thread(strategy.disconnect)
                except Exception:
                    pass

        logger.info(
            f"Sync complete: {result.n_upserted} upserted, {len(result.errors)} errors"
        )
        return result
