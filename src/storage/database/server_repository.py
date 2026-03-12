"""
MongoDB repository for server documents.

All CRUD operations for the 'servers' collection live here,
including maintenance sub-document management.
"""

import logging
from typing import List, Optional

from ...models.api_responses import MaintenanceInfo
from ...models.server_document import ServerDocument
from .mongo_client import MongoDatabase

logger = logging.getLogger(__name__)

COLLECTION = "servers"


class ServerRepository:
    """
    Data access layer for the MongoDB 'servers' collection.

    Upsert strategy: hardware fields are always overwritten by the CronJob,
    but the maintenance sub-document is only set to null on first insert
    (preserved on subsequent upserts).
    """

    def __init__(self, mongo_db: MongoDatabase):
        self._mongo_db = mongo_db

    @property
    def _collection(self):
        return self._mongo_db.db[COLLECTION]

    async def upsert_server(self, doc: ServerDocument) -> None:
        """
        Insert or update a server document from the CronJob sync.

        Uses $set for all hardware fields and $setOnInsert for maintenance
        so existing maintenance records survive daily re-syncs.
        """
        raw = doc.model_dump(by_alias=True)
        server_id = raw.pop("_id")
        raw.pop("maintenance", None)   # Never overwrite maintenance via CronJob

        await self._collection.update_one(
            {"_id": server_id},
            {
                "$set": raw,
                "$setOnInsert": {"maintenance": None},
            },
            upsert=True,
        )
        logger.debug(f"Upserted server: {server_id}")

    async def get_all_servers(self) -> List[ServerDocument]:
        """Return all server documents from MongoDB."""
        cursor = self._collection.find({})
        docs = []
        async for raw in cursor:
            docs.append(ServerDocument.model_validate(raw))
        logger.debug(f"Retrieved {len(docs)} server documents from MongoDB")
        return docs

    async def get_server(self, name: str) -> Optional[ServerDocument]:
        """Return a single server document by name."""
        raw = await self._collection.find_one({"_id": name})
        if raw:
            return ServerDocument.model_validate(raw)
        return None

    async def set_maintenance(self, name: str, info: MaintenanceInfo) -> None:
        """Embed maintenance record into the server document."""
        result = await self._collection.update_one(
            {"_id": name},
            {"$set": {"maintenance": info.model_dump()}},
        )
        if result.matched_count == 0:
            raise ValueError(f"Server '{name}' not found in MongoDB")
        logger.info(f"Maintenance set for server: {name}")

    async def remove_maintenance(self, name: str) -> None:
        """Clear the maintenance record from the server document."""
        result = await self._collection.update_one(
            {"_id": name},
            {"$set": {"maintenance": None}},
        )
        if result.matched_count == 0:
            raise ValueError(f"Server '{name}' not found in MongoDB")
        logger.info(f"Maintenance removed for server: {name}")
