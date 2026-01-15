"""
Kubernetes repository for agent data access.

Provides abstraction for querying Kubernetes Agent CRDs to determine
which servers are installed.
"""

from typing import Dict, List, Optional
import logging
from ..filters import AgentFilter, AgentConfig, AgentInfo

logger = logging.getLogger(__name__)


class KubernetesRepository:
    """
    Repository for Kubernetes agent data.

    Wraps AgentFilter to provide a clean data access interface.
    """

    def __init__(self, agent_config: AgentConfig):
        """
        Initialize Kubernetes repository.

        Args:
            agent_config: AgentConfig with cluster credentials
        """
        self.agent_config = agent_config
        self._agent_filter: Optional[AgentFilter] = None

    def _get_agent_filter(self) -> AgentFilter:
        """
        Lazy-initialize AgentFilter.

        Returns:
            AgentFilter instance
        """
        if self._agent_filter is None:
            self._agent_filter = AgentFilter(self.agent_config)
        return self._agent_filter

    async def get_installed_servers_by_cluster(self) -> Dict[str, List[str]]:
        """
        Query K8s for installed servers grouped by cluster.

        Returns:
            Dictionary mapping cluster names to lists of installed server names

        Example:
            {
                "cluster1": ["server-l4-01", "server-l4-02"],
                "cluster2": ["server-l4-03"]
            }
        """
        agent_filter = self._get_agent_filter()
        return agent_filter.get_installed_servers_by_cluster()

    async def get_agent_details(self) -> Dict[str, AgentInfo]:
        """
        Get detailed agent information.

        Returns:
            Dictionary mapping normalized server names to AgentInfo objects

        Example:
            {
                "server-l4-01": AgentInfo(
                    server_name="server-l4-01",
                    management_cluster="cluster1",
                    deployment_cluster="prod-cluster"
                )
            }
        """
        agent_filter = self._get_agent_filter()
        return agent_filter.get_agent_details()

    async def get_all_installed_servers(self) -> List[str]:
        """
        Get list of all installed server names (flattened).

        Returns:
            List of installed server names
        """
        installed_by_cluster = await self.get_installed_servers_by_cluster()
        all_servers = []
        for servers in installed_by_cluster.values():
            all_servers.extend(servers)
        return all_servers
