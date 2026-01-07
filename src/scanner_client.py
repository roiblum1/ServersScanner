import logging
import os
from typing import Dict, List, Optional
from src.server_strategy import VendorType, VendorStrategyFactory, ServerProfile
from src.kubernetes_bmh_filter import KubernetesBMHFilter, KubernetesConfig

logger = logging.getLogger(__name__)


class ServerScanner:
    """Main scanner that queries all configured vendors"""

    def __init__(self,
                 oneview_ip=None,
                 oneview_username=None,
                 oneview_password=None,
                 ome_ip=None,
                 ome_username=None,
                 ome_password=None,
                 ucs_central_ip=None,
                 central_username=None,
                 central_password=None,
                 manager_username=None,
                 manager_password=None,
                 k8s_config: Optional[KubernetesConfig] = None):
        """
        Initialize server scanner with credentials for all systems.

        Args:
            oneview_ip: HP OneView IP address
            oneview_username: HP OneView username
            oneview_password: HP OneView password
            ome_ip: Dell OME IP address
            ome_username: Dell OME username
            ome_password: Dell OME password
            ucs_central_ip: Cisco UCS Central IP address
            central_username: UCS Central username
            central_password: UCS Central password
            manager_username: UCS Manager username
            manager_password: UCS Manager password
            k8s_config: Optional Kubernetes configuration for BMH filtering
        """
        self._credentials = {
            VendorType.HP: {
                "ip": oneview_ip,
                "username": oneview_username,
                "password": oneview_password
            },
            VendorType.DELL: {
                "ip": ome_ip,
                "username": ome_username,
                "password": ome_password
            },
            VendorType.CISCO: {
                "central_ip": ucs_central_ip,
                "central_username": central_username,
                "central_password": central_password,
                "manager_username": manager_username,
                "manager_password": manager_password
            }
        }
        self._strategies = {}
        self._k8s_filter: Optional[KubernetesBMHFilter] = None

        # Initialize Kubernetes BMH filter if configured
        if k8s_config and k8s_config.cluster_names:
            try:
                self._k8s_filter = KubernetesBMHFilter(k8s_config)
                if self._k8s_filter.is_configured():
                    logger.info("Kubernetes BMH filter configured")
                else:
                    logger.warning("Kubernetes BMH filter not properly configured")
                    self._k8s_filter = None
            except Exception as e:
                logger.error(f"Failed to initialize Kubernetes BMH filter: {e}")
                self._k8s_filter = None

        self._initialize_strategies()

    def _initialize_strategies(self):
        """Initialize strategies for all configured vendors"""
        for vendor_type, credentials in self._credentials.items():
            try:
                strategy = VendorStrategyFactory.create_strategy(vendor_type, credentials)
                if strategy.is_configured():
                    self._strategies[vendor_type] = strategy
                    logger.info(f"Initialized strategy for {vendor_type.value}")
            except Exception as e:
                logger.error(f"Error initializing strategy for {vendor_type.value}: {str(e)}")

    def scan(self,
             pattern: str = r"^ocp4-hypershift-.*",
             vendors: Optional[List[str]] = None,
             filter_installed: bool = True) -> Dict[str, List[ServerProfile]]:
        """
        Scan all configured vendors for server profiles matching pattern.

        Args:
            pattern: Regex pattern to match server names
            vendors: Optional list of vendors to scan (HP, DELL, CISCO)
            filter_installed: If True and K8S is configured, filter out already-installed servers

        Returns:
            Dict mapping vendor name to list of ServerProfile (available servers only if filtering enabled)
        """
        results: Dict[str, List[ServerProfile]] = {}

        for vendor_type, strategy in self._strategies.items():
            # Skip if vendor filter specified and this vendor not in list
            if vendors and vendor_type.value not in [v.upper() for v in vendors]:
                continue

            try:
                profiles = strategy.get_server_profiles(pattern)
                results[vendor_type.value] = profiles
                logger.info(f"Found {len(profiles)} profiles in {vendor_type.value}")
            except Exception as e:
                logger.error(f"Error scanning {vendor_type.value}: {e}")
                results[vendor_type.value] = []
            finally:
                strategy.disconnect()

        # Filter out installed servers if K8S filter is configured
        if filter_installed and self._k8s_filter:
            results = self._filter_installed_servers(results)

        return results

    def _filter_installed_servers(self, results: Dict[str, List[ServerProfile]]) -> Dict[str, List[ServerProfile]]:
        """
        Filter out servers that are already installed (exist as BMH in Kubernetes).

        Args:
            results: Original scan results

        Returns:
            Filtered results with only available (not installed) servers
        """
        # Get all server names from scan results
        all_server_names = set()
        for profiles in results.values():
            for profile in profiles:
                all_server_names.add(profile.name)

        # Get installed servers from Kubernetes
        installed_servers = self._k8s_filter.get_installed_servers()

        # Filter results
        filtered_results: Dict[str, List[ServerProfile]] = {}
        for vendor, profiles in results.items():
            available_profiles = [
                p for p in profiles
                if p.name not in installed_servers
            ]
            filtered_results[vendor] = available_profiles

            installed_count = len(profiles) - len(available_profiles)
            if installed_count > 0:
                logger.info(f"{vendor}: Filtered out {installed_count} installed servers, {len(available_profiles)} available")

        return filtered_results

    def find_duplicates(self, results: Dict[str, List[ServerProfile]]) -> List[str]:
        """Find profile names that exist in multiple vendors"""
        name_vendors: Dict[str, List[str]] = {}

        for vendor, profiles in results.items():
            for profile in profiles:
                if profile.name not in name_vendors:
                    name_vendors[profile.name] = []
                name_vendors[profile.name].append(vendor)

        duplicates = [
            name for name, vendors in name_vendors.items()
            if len(vendors) > 1
        ]

        return duplicates

    def disconnect(self):
        """Disconnect from all systems"""
        for vendor_type, strategy in self._strategies.items():
            try:
                strategy.disconnect()
                strategy.clear_cache()
            except Exception as e:
                logger.warning(f"Error disconnecting from {vendor_type.value}: {str(e)}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup"""
        self.disconnect()


def initialize_scanner():
    """Initialize the scanner using environment variables"""
    oneview_ip = os.getenv("ONEVIEW_IP")
    oneview_username = os.getenv("ONEVIEW_USERNAME", "administrator")
    oneview_password = os.getenv("ONEVIEW_PASSWORD")

    ome_ip = os.getenv("OME_IP")
    ome_username = os.getenv("OME_USERNAME", "admin")
    ome_password = os.getenv("OME_PASSWORD")

    ucs_central_ip = os.getenv("UCS_CENTRAL_IP")
    central_username = os.getenv("UCS_CENTRAL_USERNAME", "admin")
    central_password = os.getenv("UCS_CENTRAL_PASSWORD")
    manager_username = os.getenv("UCS_MANAGER_USERNAME", "admin")
    manager_password = os.getenv("UCS_MANAGER_PASSWORD")

    # Initialize Kubernetes BMH filter config if available
    k8s_config = None
    k8s_cluster_names = os.getenv("K8S_CLUSTER_NAMES")
    k8s_domain_name = os.getenv("K8S_DOMAIN_NAME")

    if k8s_cluster_names and k8s_domain_name:
        k8s_config = KubernetesConfig(
            cluster_names=k8s_cluster_names,
            domain_name=k8s_domain_name,
            username=os.getenv("K8S_USERNAME"),
            password=os.getenv("K8S_PASSWORD"),
            token=os.getenv("K8S_TOKEN"),
            namespace=os.getenv("K8S_NAMESPACE", "inventory")
        )

    scanner = ServerScanner(
        oneview_ip=oneview_ip,
        oneview_username=oneview_username,
        oneview_password=oneview_password,
        ome_ip=ome_ip,
        ome_username=ome_username,
        ome_password=ome_password,
        ucs_central_ip=ucs_central_ip,
        central_username=central_username,
        central_password=central_password,
        manager_username=manager_username,
        manager_password=manager_password,
        k8s_config=k8s_config
    )

    return scanner
