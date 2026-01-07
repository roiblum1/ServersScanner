import logging
from typing import Set, Optional
from dataclasses import dataclass
from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


@dataclass
class KubernetesConfig:
    """Kubernetes cluster configuration"""
    cluster_names: str  # Comma-separated list of cluster names
    domain_name: str
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    namespace: str = "inventory"


class KubernetesBMHFilter:
    """
    Kubernetes BareMetalHost filter to identify already-installed servers.
    Queries BMH resources from Kubernetes clusters and filters them from scan results.
    """

    # BareMetalHost CRD details (Metal3)
    BMH_GROUP = "metal3.io"
    BMH_VERSION = "v1alpha1"
    BMH_PLURAL = "baremetalhosts"

    def __init__(self, config: KubernetesConfig):
        self.config = config
        self._installed_servers: Optional[Set[str]] = None

    def is_configured(self) -> bool:
        """Check if Kubernetes credentials are configured"""
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
        Get set of server names that are already installed (exist as BMH resources).
        Returns: Set of server profile names
        """
        if self._installed_servers is not None:
            return self._installed_servers

        self._installed_servers = set()
        cluster_list = [c.strip() for c in self.config.cluster_names.split(',')]

        logger.info(f"Checking BMH resources across {len(cluster_list)} Kubernetes clusters...")

        for cluster_name in cluster_list:
            if not cluster_name:
                continue

            api_server = f"https://api.{cluster_name}.{self.config.domain_name}:6443"
            logger.info(f"Querying cluster: {cluster_name} at {api_server}")

            try:
                bmh_names = self._get_bmh_from_cluster(api_server, cluster_name)
                if bmh_names:
                    logger.info(f"Found {len(bmh_names)} BMH resources in cluster '{cluster_name}'")
                    self._installed_servers.update(bmh_names)
                else:
                    logger.info(f"No BMH resources found in cluster '{cluster_name}'")
            except Exception as e:
                logger.warning(f"Failed to query cluster '{cluster_name}': {e}")

        logger.info(f"Total installed servers across all clusters: {len(self._installed_servers)}")
        return self._installed_servers

    def _get_bmh_from_cluster(self, api_server: str, cluster_name: str) -> Set[str]:
        """
        Query BareMetalHost resources from a specific cluster using Python Kubernetes client.
        Returns: Set of BMH names
        """
        bmh_names = set()

        try:
            # Create custom configuration for this cluster
            configuration = client.Configuration()
            configuration.host = api_server
            configuration.verify_ssl = False  # Disable SSL verification for internal clusters

            # Configure authentication
            if self.config.token:
                configuration.api_key = {"authorization": f"Bearer {self.config.token}"}
            elif self.config.username and self.config.password:
                configuration.username = self.config.username
                configuration.password = self.config.password
            else:
                logger.error(f"No valid authentication method configured for cluster {cluster_name}")
                return bmh_names

            # Create API client
            api_client = client.ApiClient(configuration)
            custom_api = client.CustomObjectsApi(api_client)

            logger.debug(f"Querying BareMetalHost resources in namespace '{self.config.namespace}'")

            # Query BareMetalHost custom resources
            try:
                bmh_list = custom_api.list_namespaced_custom_object(
                    group=self.BMH_GROUP,
                    version=self.BMH_VERSION,
                    namespace=self.config.namespace,
                    plural=self.BMH_PLURAL,
                    _request_timeout=30
                )

                # Extract BMH names
                for item in bmh_list.get("items", []):
                    metadata = item.get("metadata", {})
                    name = metadata.get("name")
                    if name:
                        bmh_names.add(name)
                        logger.debug(f"Found BMH: {name}")

            except ApiException as e:
                if e.status == 404:
                    logger.warning(f"BareMetalHost CRD not found in cluster '{cluster_name}' - cluster may not have Metal3 installed")
                else:
                    logger.error(f"Kubernetes API error querying BMH in cluster '{cluster_name}': {e.status} - {e.reason}")
            finally:
                # Clean up API client
                api_client.close()

        except Exception as e:
            logger.error(f"Error connecting to cluster '{cluster_name}': {type(e).__name__}: {e}")

        return bmh_names

    def filter_available_servers(self, all_servers: Set[str]) -> Set[str]:
        """
        Filter out installed servers from the total set.
        Returns: Set of available (not installed) servers
        """
        installed = self.get_installed_servers()
        available = all_servers - installed

        logger.info(f"Total servers: {len(all_servers)}")
        logger.info(f"Installed servers: {len(installed)}")
        logger.info(f"Available servers: {len(available)}")

        return available

    def clear_cache(self):
        """Clear cached BMH data"""
        self._installed_servers = None
