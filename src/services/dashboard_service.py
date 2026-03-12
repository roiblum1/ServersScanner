"""
Dashboard service — assembles dashboard data from MongoDB + live K8s queries.

Read path:
  1. Fetch all server documents from MongoDB (fast)
  2. Query Kubernetes live for current installation status (frequently changing)
  3. Merge: maintenance from MongoDB doc, status from K8s lookup
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

import math

from ..models.api_responses import (
    CacheInfo,
    ClusterStats,
    DashboardData,
    PaginationInfo,
    ServerInfo,
    ZoneData,
)
from ..repositories.kubernetes_repository import KubernetesRepository
from ..storage.database.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Business logic for dashboard data assembly.

    Reads server profiles from MongoDB and overlays live Kubernetes
    installation status on every request.
    """

    def __init__(
        self,
        server_repo: ServerRepository,
        k8s_repo: KubernetesRepository,
        cache_ttl: int,
    ):
        self.server_repo = server_repo
        self.k8s_repo = k8s_repo
        self.cache_ttl = cache_ttl

    async def build_dashboard(
        self,
        zone_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 500,
    ) -> DashboardData:
        """
        Build complete dashboard data.

        1. Load all server documents from MongoDB
        2. Query Kubernetes live
        3. Paginate, assemble, and return DashboardData
        """
        logger.info("Loading server data from MongoDB...")
        docs = await self.server_repo.get_all_servers()

        if zone_filter:
            allowed = {z.strip().lower() for z in zone_filter.split(",") if z.strip()}
            docs = [d for d in docs if not d.zone or d.zone.lower() in allowed]

        # Pagination — sort first so pages are stable
        total = len(docs)
        docs.sort(key=lambda d: d.id)
        offset = (page - 1) * page_size
        docs = docs[offset: offset + page_size]
        total_pages = math.ceil(total / page_size) if page_size else 1
        pagination = PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

        if self.k8s_repo is not None:
            logger.info(f"Querying Kubernetes for installed servers ({len(docs)} MongoDB docs)...")
            installed_by_cluster = await self.k8s_repo.get_installed_servers_by_cluster()
            agent_details = await self.k8s_repo.get_agent_details()
        else:
            logger.info("Kubernetes not configured — skipping K8s live queries")
            installed_by_cluster = {}
            agent_details = {}

        return self._assemble_dashboard(docs, installed_by_cluster, agent_details, pagination)

    def _assemble_dashboard(
        self,
        docs,
        installed_by_cluster: Dict[str, List[str]],
        agent_details: Dict,
        pagination: PaginationInfo,
    ) -> DashboardData:
        """Merge MongoDB documents with live K8s data into DashboardData."""
        all_installed: set = set()
        for servers in installed_by_cluster.values():
            all_installed.update(servers)

        # Group docs by zone → vendor
        zone_vendor: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for doc in docs:
            zone = doc.zone or "Unknown"
            zone_vendor[zone][doc.vendor].append(doc)

        zones_data = []
        for zone in sorted(zone_vendor.keys()):
            vendors_data = {}
            for vendor in sorted(zone_vendor[zone].keys()):
                servers_info = []
                for doc in sorted(zone_vendor[zone][vendor], key=lambda d: d.id):
                    normalized = doc.id.lower().strip()

                    # Always resolve K8s cluster info — maintenance doesn't hide it
                    if normalized in all_installed:
                        cluster = next(
                            (c for c, srvs in installed_by_cluster.items() if normalized in srvs),
                            None,
                        )
                        agent = agent_details.get(normalized)
                        deployment_cluster = getattr(agent, "deployment_cluster", None) if agent else None
                    else:
                        cluster = None
                        deployment_cluster = None

                    # Status: maintenance takes priority over installed/available
                    if doc.maintenance is not None:
                        status = "maintenance"
                    elif cluster is not None:
                        status = "installed"
                    else:
                        status = "available"

                    servers_info.append(ServerInfo(
                        name=doc.id,
                        vendor=vendor,
                        zone=zone if zone != "Unknown Zone" else "Unknown",
                        status=status,
                        cluster=cluster,
                        deployment_cluster=deployment_cluster,
                        maintenance=doc.maintenance,
                        # Hardware fields from MongoDB
                        bmc_address=doc.bmc_address,
                        mac_address=doc.mac_address,
                        cpu_model=doc.cpu_model,
                        cpu_count=doc.cpu_count,
                        cpu_cores=doc.cpu_cores,
                        memory_gb=doc.memory_gb,
                        model=doc.model,
                        serial=doc.serial,
                        total_disk_gb=doc.total_disk_gb,
                    ))

                vendors_data[vendor] = servers_info

            zones_data.append(ZoneData(
                zone=zone if zone != "Unknown Zone" else "Unknown",
                vendors=vendors_data,
            ))

        # Cluster stats
        cluster_stats = [
            ClusterStats(
                cluster_name=cn,
                installed_count=len(srvs),
                servers=sorted(srvs),
            )
            for cn, srvs in installed_by_cluster.items()
        ]

        available_count = sum(
            1
            for z in zones_data
            for vendor_servers in z.vendors.values()
            for s in vendor_servers
            if s.status == "available"
        )

        summary = {
            "total_available": available_count,
            "total_installed": sum(len(s) for s in installed_by_cluster.values()),
            "total_clusters": len(installed_by_cluster),
            "total_zones": len(zones_data),
        }

        logger.info(
            f"Dashboard assembled: {len(zones_data)} zones, "
            f"{summary['total_installed']} installed, "
            f"{summary['total_available']} available"
        )

        return DashboardData(
            zones=zones_data,
            clusters=cluster_stats,
            summary=summary,
            cache_info=CacheInfo(
                cached=False,
                age_seconds=0,
                next_refresh_seconds=self.cache_ttl,
            ),
            pagination=pagination,
        )
