"""
API response models for FastAPI endpoints.

Provides type-safe Pydantic models for all API responses with validation.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal


class MaintenanceInfo(BaseModel):
    """Maintenance record for a server"""
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for maintenance")
    severity: Literal["critical", "high", "medium", "low"] = Field(..., description="Severity level")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    created_by: Optional[str] = Field(None, description="User who created the maintenance record")


class ServerInfo(BaseModel):
    """Server information with status, hardware details, and maintenance."""
    name: str = Field(..., min_length=1)
    vendor: str
    zone: Optional[str] = None
    status: Literal["available", "installed", "maintenance"]
    cluster: Optional[str] = None
    deployment_cluster: Optional[str] = None
    maintenance: Optional[MaintenanceInfo] = None

    # Hardware details (from MongoDB, populated by CronJob)
    bmc_address: Optional[str] = None
    mac_address: Optional[str] = None
    cpu_model: Optional[str] = None
    cpu_count: Optional[int] = None
    cpu_cores: Optional[int] = None
    memory_gb: Optional[float] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    total_disk_gb: Optional[float] = None


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., ge=1, description="Current page (1-based)")
    page_size: int = Field(..., ge=1, description="Servers per page")
    total: int = Field(..., ge=0, description="Total matching servers")
    total_pages: int = Field(..., ge=0, description="Total pages")


class ZoneData(BaseModel):
    """Servers grouped by zone"""
    zone: str = Field(..., description="Zone name")
    vendors: Dict[str, List[ServerInfo]] = Field(..., description="Servers grouped by vendor")


class ClusterStats(BaseModel):
    """Statistics per cluster"""
    cluster_name: str = Field(..., description="Cluster name")
    installed_count: int = Field(..., ge=0, description="Number of installed servers")
    servers: List[str] = Field(..., description="List of server names")


class CacheInfo(BaseModel):
    """Cache metadata"""
    cached: bool = Field(..., description="Whether data is from cache")
    age_seconds: int = Field(..., ge=0, description="Age of cached data in seconds")
    next_refresh_seconds: int = Field(..., ge=0, description="Seconds until next refresh")


class DashboardData(BaseModel):
    """Complete dashboard data"""
    zones: List[ZoneData] = Field(..., description="Servers grouped by zone")
    clusters: List[ClusterStats] = Field(..., description="Cluster statistics")
    summary: Dict[str, int] = Field(..., description="Summary statistics")
    cache_info: CacheInfo = Field(..., description="Cache metadata")
    pagination: Optional[PaginationInfo] = Field(None, description="Pagination metadata")


class StatusResponse(BaseModel):
    """Generic status response"""
    status: Literal["success", "error", "removed"] = Field(..., description="Operation status")
    message: Optional[str] = Field(None, description="Status message")
    server: Optional[str] = Field(None, description="Server name")


class CacheEntryStatus(BaseModel):
    """Status of a single cache entry"""
    age_seconds: int = Field(..., ge=0, description="Age of cache entry")
    expired: bool = Field(..., description="Whether entry is expired")
    is_scanning: bool = Field(..., description="Whether scan is in progress")
    next_refresh_seconds: int = Field(..., ge=0, description="Seconds until next refresh")


class CacheStatusResponse(BaseModel):
    """Complete cache status response"""
    cache_ttl_seconds: int = Field(..., ge=0, description="Cache TTL in seconds")
    entries: Dict[str, CacheEntryStatus] = Field(..., description="Status of each cache entry")


class ClustersResponse(BaseModel):
    """List of configured clusters"""
    clusters: List[str] = Field(..., description="List of cluster names")


class ZonesResponse(BaseModel):
    """List of discovered zones"""
    zones: List[str] = Field(..., description="List of zone names")
    cached: bool = Field(..., description="Whether data is from cache")


class ServerDetailsResponse(BaseModel):
    """Single server details"""
    name: str = Field(..., description="Server name")
    maintenance: Optional[MaintenanceInfo] = Field(None, description="Maintenance details if exists")
