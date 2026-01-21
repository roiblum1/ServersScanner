"""
API response models for FastAPI endpoints.

Provides type-safe Pydantic models for all API responses with validation.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal


class MaintenanceInfo(BaseModel):
    """Maintenance record for a server"""
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for maintenance")
    severity: Literal["critical", "high", "medium", "low"] = Field(..., description="Severity level")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    created_by: Optional[str] = Field(None, description="User who created the maintenance record")


class ServerInfo(BaseModel):
    """Server information with installation status"""
    name: str = Field(..., min_length=1, description="Server profile name")
    vendor: str = Field(..., description="Vendor name (HP, DELL, CISCO)")
    zone: Optional[str] = Field(None, description="Zone/location name")
    status: Literal["available", "installed", "maintenance"] = Field(..., description="Server status")
    cluster: Optional[str] = Field(None, description="Management cluster the agent is on")
    deployment_cluster: Optional[str] = Field(None, description="Cluster the agent is deployed to")
    maintenance: Optional[MaintenanceInfo] = Field(None, description="Maintenance details if in maintenance mode")


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
