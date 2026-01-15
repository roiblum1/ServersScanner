"""
Dashboard service for business logic orchestration.

Coordinates scanning, data assembly, and maintenance status refreshing
for the dashboard.
"""

from typing import Optional, Dict, List
import asyncio
import logging
import os
from ..models.api_responses import (
    DashboardData,
    ZoneData,
    ClusterStats,
    ServerInfo,
    MaintenanceInfo,
    CacheInfo
)
from ..services.scanner_service import initialize_scanner
from ..repositories.maintenance_repository import MaintenanceRepository
from ..repositories.kubernetes_repository import KubernetesRepository

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Business logic for dashboard data assembly.

    Orchestrates vendor scanning, Kubernetes queries, and maintenance
    status to build complete dashboard data.
    """

    def __init__(
        self,
        maintenance_repo: MaintenanceRepository,
        k8s_repo: KubernetesRepository,
        cache_ttl: int
    ):
        """
        Initialize dashboard service.

        Args:
            maintenance_repo: Repository for maintenance data
            k8s_repo: Repository for Kubernetes agent data
            cache_ttl: Cache TTL in seconds
        """
        self.maintenance_repo = maintenance_repo
        self.k8s_repo = k8s_repo
        self.cache_ttl = cache_ttl

    async def build_dashboard(
        self,
        zone_filter: Optional[str] = None
    ) -> DashboardData:
        """
        Build complete dashboard data.

        Orchestrates:
        1. Vendor scanning
        2. Kubernetes agent queries
        3. Maintenance status loading
        4. Data assembly

        Args:
            zone_filter: Optional comma-separated list of zones to filter

        Returns:
            DashboardData ready for frontend
        """
        # Override zone filter if provided
        if zone_filter:
            os.environ["ZONES"] = zone_filter

        # Initialize scanner
        logger.info("Initializing scanner...")
        scanner = initialize_scanner()

        # Get all servers (without filtering installed ones)
        logger.info("Scanning vendors for all servers...")
        all_results = scanner.scan(filter_installed=False)

        # Get installed servers per cluster
        logger.info("Querying Kubernetes for installed servers...")
        installed_by_cluster = await self.k8s_repo.get_installed_servers_by_cluster()

        # Get agent details (including deployment clusters)
        agent_details = await self.k8s_repo.get_agent_details()

        # Load maintenance records
        logger.info("Loading maintenance records...")
        maintenance_records = await self.maintenance_repo.get_all()

        # Assemble dashboard
        dashboard_data = await self._assemble_dashboard(
            all_results,
            installed_by_cluster,
            agent_details,
            maintenance_records
        )

        logger.info(f"Dashboard built: {len(dashboard_data.zones)} zones, {dashboard_data.summary['total_installed']} installed")
        return dashboard_data

    async def _assemble_dashboard(
        self,
        all_results,
        installed_by_cluster: Dict[str, List[str]],
        agent_details: Dict,
        maintenance_records: Dict[str, MaintenanceInfo]
    ) -> DashboardData:
        """
        Assemble dashboard data from components.

        Args:
            all_results: ScanResults with all servers
            installed_by_cluster: Dict mapping cluster to installed server names
            agent_details: Dict mapping server name to AgentInfo
            maintenance_records: Dict mapping server name to MaintenanceInfo

        Returns:
            Complete DashboardData
        """
        # Flatten installed servers to set for quick lookup
        all_installed = set()
        for servers in installed_by_cluster.values():
            all_installed.update(servers)

        # Build zone data
        zones_data = []
        for zone in all_results.get_zones():
            vendors_data = {}

            for vendor in all_results.get_vendors_in_zone(zone):
                profiles = all_results.get_profiles(zone, vendor)
                servers_info = []

                for profile in sorted(profiles, key=lambda p: p.name):
                    # Determine status and cluster
                    status = "available"
                    cluster = None
                    deployment_cluster = None
                    maintenance_info = None

                    # Normalize for case-insensitive comparison
                    normalized_name = profile.name.lower().strip()

                    # Check maintenance FIRST (highest priority)
                    if normalized_name in maintenance_records:
                        status = "maintenance"
                        maintenance_info = maintenance_records[normalized_name]
                    elif normalized_name in all_installed:
                        status = "installed"
                        # Find which management cluster
                        for cluster_name, servers in installed_by_cluster.items():
                            if normalized_name in servers:
                                cluster = cluster_name
                                break

                        # Get deployment cluster from agent details
                        if normalized_name in agent_details:
                            agent_info = agent_details[normalized_name]
                            deployment_cluster = agent_info.deployment_cluster

                    servers_info.append(ServerInfo(
                        name=profile.name,
                        vendor=vendor,
                        zone=zone,
                        status=status,
                        cluster=cluster,
                        deployment_cluster=deployment_cluster,
                        maintenance=maintenance_info
                    ))

                vendors_data[vendor] = servers_info

            zones_data.append(ZoneData(
                zone=zone if zone != "Unknown Zone" else "Unknown",
                vendors=vendors_data
            ))

        # Build cluster stats
        cluster_stats = []
        for cluster_name, servers in installed_by_cluster.items():
            cluster_stats.append(ClusterStats(
                cluster_name=cluster_name,
                installed_count=len(servers),
                servers=sorted(servers)
            ))

        # Build summary
        total_servers = sum(len(servers) for servers in installed_by_cluster.values())
        available_count = sum(
            len([s for s in vendor_servers if s.status == "available"])
            for zone in zones_data
            for vendor_servers in zone.vendors.values()
        )

        summary = {
            "total_available": available_count,
            "total_installed": total_servers,
            "total_clusters": len(installed_by_cluster),
            "total_zones": len(zones_data)
        }

        return DashboardData(
            zones=zones_data,
            clusters=cluster_stats,
            summary=summary,
            cache_info=CacheInfo(
                cached=False,
                age_seconds=0,
                next_refresh_seconds=self.cache_ttl
            )
        )

    async def refresh_maintenance(self, dashboard_data: DashboardData) -> DashboardData:
        """
        Refresh maintenance status in cached dashboard data.

        Hybrid caching: vendor data cached (expensive), maintenance fresh (cheap).

        Args:
            dashboard_data: Existing dashboard data from cache

        Returns:
            DashboardData with refreshed maintenance status
        """
        logger.info("Refreshing maintenance status in cached data...")

        # Load current maintenance records
        maintenance_records = await self.maintenance_repo.get_all()

        # Update maintenance status for all servers
        for zone in dashboard_data.zones:
            for vendor, servers in zone.vendors.items():
                for server in servers:
                    normalized = server.name.lower().strip()

                    if normalized in maintenance_records:
                        # Server is now in maintenance
                        server.status = "maintenance"
                        server.maintenance = maintenance_records[normalized]
                    elif server.maintenance is not None:
                        # Server was in maintenance but no longer
                        server.status = "installed" if server.cluster else "available"
                        server.maintenance = None

        logger.info("Maintenance status refreshed")
        return dashboard_data
