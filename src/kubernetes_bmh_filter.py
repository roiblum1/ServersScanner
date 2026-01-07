import logging
import subprocess
import json
from typing import Set, Optional
from dataclasses import dataclass

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
                bmh_names = self._get_bmh_from_cluster(api_server)
                if bmh_names:
                    logger.info(f"Found {len(bmh_names)} BMH resources in cluster '{cluster_name}'")
                    self._installed_servers.update(bmh_names)
                else:
                    logger.info(f"No BMH resources found in cluster '{cluster_name}'")
            except Exception as e:
                logger.warning(f"Failed to query cluster '{cluster_name}': {e}")

        logger.info(f"Total installed servers across all clusters: {len(self._installed_servers)}")
        return self._installed_servers

    def _get_bmh_from_cluster(self, api_server: str) -> Set[str]:
        """
        Query BareMetalHost resources from a specific cluster.
        Returns: Set of BMH names
        """
        cmd = [
            "kubectl", "get", "baremetalhosts",
            "-n", self.config.namespace,
            "-o", "json",
            "--server", api_server
        ]

        # Add authentication
        if self.config.token:
            cmd.extend(["--token", self.config.token])
        elif self.config.username and self.config.password:
            cmd.extend(["--username", self.config.username])
            cmd.extend(["--password", self.config.password])

        # Disable certificate verification for internal clusters
        cmd.append("--insecure-skip-tls-verify")

        logger.debug(f"Executing: kubectl get baremetalhosts -n {self.config.namespace} --server {api_server}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )

            data = json.loads(result.stdout)
            items = data.get("items", [])

            bmh_names = set()
            for item in items:
                name = item.get("metadata", {}).get("name")
                if name:
                    bmh_names.add(name)
                    logger.debug(f"Found BMH: {name}")

            return bmh_names

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout querying cluster at {api_server}")
            return set()
        except subprocess.CalledProcessError as e:
            logger.error(f"kubectl command failed: {e.stderr}")
            return set()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse kubectl output: {e}")
            return set()
        except Exception as e:
            logger.error(f"Unexpected error querying BMH: {e}")
            return set()

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
