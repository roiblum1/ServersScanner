"""
MongoDB async client wrapper using Motor.
"""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class MongoDatabase:
    """
    Lifecycle wrapper around an async Motor client.

    Call connect() on app startup and disconnect() on shutdown.
    """

    def __init__(self, uri: str, db_name: str, tls_verify: bool = True):
        self.uri = uri
        self.db_name = db_name
        self.tls_verify = tls_verify
        self._client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        kwargs = {}
        if not self.tls_verify:
            kwargs["tlsAllowInvalidCertificates"] = True
        self._client = AsyncIOMotorClient(self.uri, **kwargs)
        await self._client.admin.command("ping")
        logger.info(f"Connected to MongoDB database '{self.db_name}' (TLS verify: {self.tls_verify})")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Disconnected from MongoDB")

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if not self._client:
            raise RuntimeError("MongoDB client is not connected. Call connect() first.")
        return self._client[self.db_name]
