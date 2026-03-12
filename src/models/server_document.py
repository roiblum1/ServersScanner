"""
ServerDocument - Pydantic model for MongoDB server documents.

This is the shared contract between the CronJob write path
(vendor API → MongoDB) and the API read path (MongoDB → dashboard).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .api_responses import MaintenanceInfo


class DiskInfo(BaseModel):
    """Disk/storage device information"""
    size_gb: Optional[float] = None
    type: Optional[str] = None   # "SSD", "HDD", etc.
    model: Optional[str] = None
    count: Optional[int] = None


class ServerDocument(BaseModel):
    """
    Full server profile stored in MongoDB.

    _id is the server profile name (unique across all vendors).
    maintenance is preserved across CronJob upserts — only set to null on first insert.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", description="Server profile name (MongoDB _id)")
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
    disks: List[Dict[str, Any]] = Field(default_factory=list)

    # Maintenance (written by API, preserved by CronJob upserts)
    maintenance: Optional[MaintenanceInfo] = None

    # Audit
    last_scanned: Optional[datetime] = None
