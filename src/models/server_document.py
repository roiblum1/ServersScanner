"""
ServerDocument - Pydantic model for MongoDB server documents.

This is the shared contract between the CronJob write path
(vendor API → MongoDB) and the API read path (MongoDB → dashboard).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .api_responses import MaintenanceInfo


class ServerDocument(BaseModel):
    """
    Full server profile stored in MongoDB.

    _id is the server profile name (unique across all vendors).
    maintenance is preserved across CronJob upserts — only set to null on first insert.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", description="Server profile name (MongoDB _id)")

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, v: str) -> str:
        return v.lower().strip()
    vendor: str
    zone: Optional[str] = None
    bmc_address: Optional[str] = None
    mac_address: Optional[str] = None

    # Hardware details (populated by CronJob)
    cpu_model: Optional[str] = None
    cpu_count: Optional[int] = None
    cpu_cores: Optional[int] = None
    memory_gb: Optional[float] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    total_disk_gb: Optional[float] = None

    # Maintenance (written by API, preserved by CronJob upserts)
    maintenance: Optional[MaintenanceInfo] = None

    # Conflict detection (set by CronJob when >1 vendor returns the same server name)
    conflict_vendors: Optional[list[str]] = None

    # Audit
    last_scanned: Optional[datetime] = None
