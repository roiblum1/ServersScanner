"""
Kubernetes Agent CRD filter - replaces BareMetalHost filter.

Queries Agent resources from Kubernetes clusters to identify installed servers.
Uses hostname/requestedHostname logic to extract server names.
"""

import logging
from typing import Set, Optional
from dataclasses import dataclass
from kubernetes import client
from kubernetes.client.rest import ApiException

from ..parsers import HostnameParser

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """
    Kubernetes Agent filter configuration.

    Attributes:
        cluster_names: Comma-separated list of cluster names
        domain_name: Domain name for API servers
        token: Single token OR comma-separated tokens (one per cluster)
        namespace: Namespace to query (default: 'assisted-installer')
        username: Optional basic auth username (deprecated)
        password: Optional basic auth password (deprecated)
    """
    cluster_names: str
    domain_name: str
    token: Optional[str] = None
    namespace: str = "assisted-installer"
    username: Optional[str] = None
    password: Optional[str] = None

    def get_token_for_cluster(self, cluster_index: int) -> Optional[str]:
        """
        Get token for a specific cluster by index.

        Args:
            cluster_index: Index of the cluster

        Returns:
            Token for the cluster or None
        """
        if not self.token:
            return None

        tokens = [t.strip() for t in self.token.split(',')]

        # Single token for all clusters
        if len(tokens) == 1:
            return tokens[0]

        # Per-cluster tokens
        if cluster_index < len(tokens):
            return tokens[cluster_index]
        else:
            logger.warning(f"Not enough tokens. Expected {cluster_index + 1}, got {len(tokens)}")
            return None


class AgentFilter:
    """
    Kubernetes Agent CRD filter.

    Queries Agent resources from multiple Kubernetes clusters and extracts
    server names using hostname/requestedHostname logic.

    Design Pattern: Strategy pattern for filtering installed servers
    """

    # Agent CRD details
    AGENT_GROUP = "agent-install.openshift.io"
    AGENT_VERSION = "v1beta1"
    AGENT_PLURAL = "agents"

    def __init__(self, config: AgentConfig):
        """
        Initialize Agent filter.

        Args:
            config: Agent filter configuration
        """
        self.config = config
        self._installed_servers: Optional[Set[str]] = None
        self._hostname_parser = HostnameParser()

    def is_configured(self) -> bool:
        """Check if Agent filter is properly configured"""
        has_auth = bool(self.config.token) or (
            bool(self.config.username) and bool(self.config.password)
        )
        return all([
            self.config.cluster_names,
            self.config.domain_name,
            has_auth
        ])

    def get_installed_servers(self) -> Set[str]:
        """
        Get set of server names that are already installed (exist as Agent resources).

        Returns:
            Set of server names extracted from Agent resources
        """
        if self._installed_servers is not None:
            return self._installed_servers

        self._installed_servers = set()
        cluster_list = [c.strip() for c in self.config.cluster_names.split(',')]

        logger.info(f"Checking Agent resources across {len(cluster_list)} Kubernetes clusters...")

        for cluster_index, cluster_name in enumerate(cluster_list):
            if not cluster_name:
                continue

            api_server = f"https://api.{cluster_name}.{self.config.domain_name}:6443"
            logger.info(f"Querying cluster: {cluster_name} at {api_server}")

            try:
                agent_names = self._get_agents_from_cluster(api_server, cluster_name, cluster_index)
                if agent_names:
                    logger.info(f"Found {len(agent_names)} Agent resources in cluster '{cluster_name}'")
                    self._installed_servers.update(agent_names)
                else:
                    logger.info(f"No Agent resources found in cluster '{cluster_name}'")
            except Exception as e:
                logger.warning(f"Failed to query cluster '{cluster_name}': {e}")

        logger.info(f"Total installed servers across all clusters: {len(self._installed_servers)}")
        return self._installed_servers

    def _get_agents_from_cluster(self, api_server: str, cluster_name: str, cluster_index: int) -> Set[str]:
        """
        Query Agent resources from a specific cluster.

        Args:
            api_server: Kubernetes API server URL
            cluster_name: Cluster name
            cluster_index: Index of cluster (for per-cluster tokens)

        Returns:
            Set of extracted server names
        """
        server_names = set()

        try:
            # Create cluster-specific configuration
            configuration = client.Configuration()
            configuration.host = api_server
            configuration.verify_ssl = False

            # Get token for this cluster
            cluster_token = self.config.get_token_for_cluster(cluster_index)

            # Configure authentication
            if cluster_token:
                configuration.api_key = {"authorization": f"Bearer {cluster_token}"}
                logger.debug(f"Using token authentication for cluster {cluster_name} (token #{cluster_index + 1})")
            elif self.config.username and self.config.password:
                import base64
                credentials = f"{self.config.username}:{self.config.password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                configuration.api_key = {"authorization": f"Basic {encoded}"}
                logger.debug(f"Using basic authentication for cluster {cluster_name}")
                logger.warning("Basic auth is deprecated. Use token authentication instead.")
            else:
                logger.error(f"No authentication configured for cluster {cluster_name}")
                return server_names

            # Create API client
            api_client = client.ApiClient(configuration)
            custom_api = client.CustomObjectsApi(api_client)

            try:
                # Query Agent custom resources across all namespaces
                agent_list = custom_api.list_cluster_custom_object(
                    group=self.AGENT_GROUP,
                    version=self.AGENT_VERSION,
                    plural=self.AGENT_PLURAL,
                    _request_timeout=30
                )

                # Extract hostnames from Agent resources
                for item in agent_list.get("items", []):
                    hostname, requested_hostname = self._extract_agent_hostnames(item)
                    server_name = self._hostname_parser.extract_hostname(hostname, requested_hostname)

                    if server_name:
                        server_names.add(server_name)
                        logger.debug(f"Found Agent with server name: {server_name}")

            except ApiException as e:
                self._handle_api_exception(e, cluster_name, cluster_index)
            finally:
                api_client.close()

        except Exception as e:
            logger.error(f"Error connecting to cluster '{cluster_name}': {type(e).__name__}: {e}")

        return server_names

    def _extract_agent_hostnames(self, agent: dict) -> tuple[Optional[str], Optional[str]]:
        """
        Extract hostname and requestedHostname from Agent resource.

        Args:
            agent: Agent resource dict

        Returns:
            Tuple of (hostname, requestedHostname)
        """
        status = agent.get("status", {})
        inventory = status.get("inventory", {})

        hostname = inventory.get("hostname")
        requested_hostname = status.get("requestedHostname")

        return hostname, requested_hostname

    def _handle_api_exception(self, e: ApiException, cluster_name: str, cluster_index: int):
        """Handle Kubernetes API exceptions with detailed logging"""
        if e.status == 404:
            logger.warning(
                f"Agent CRD not found in cluster '{cluster_name}' - "
                f"cluster may not have Assisted Installer"
            )
        elif e.status == 403:
            logger.error(
                f"Authentication failed (403 Forbidden) for cluster '{cluster_name}' "
                f"(cluster #{cluster_index + 1})"
            )
            logger.error(f"Reason: {e.reason}")
            if self.config.username and not self.config.token:
                logger.error("Using deprecated username/password authentication.")
                logger.error("Use token authentication instead. See GET_TOKEN.md")
            else:
                logger.error(f"Token for cluster #{cluster_index + 1} may be invalid or lack permissions.")
                logger.error("Required permissions: get, list on agents.agent-install.openshift.io")
                logger.error("Tip: K8S_TOKEN=token1,token2,token3 (one per cluster)")
        elif e.status == 401:
            logger.error(f"Authentication failed (401 Unauthorized) for cluster '{cluster_name}'")
            logger.error("Credentials are invalid or expired.")
        else:
            logger.error(
                f"Kubernetes API error for cluster '{cluster_name}': "
                f"{e.status} - {e.reason}"
            )

    def clear_cache(self):
        """Clear cached Agent data"""
        self._installed_servers = None
