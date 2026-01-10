"""
Scanner Service - Main business logic for server scanning.

Coordinates vendor strategies, zone filtering, and Agent filtering.
"""

import logging
import os
from typing import Dict, List, Optional, Set
from collections import defaultdict

from ..strategies import VendorType
from ..models import ServerProfile, ZoneConfig
from ..filters import AgentFilter, AgentConfig
from ..repositories import StrategyFactory
from ..parsers import ZoneParser

logger = logging.getLogger(__name__)


class ScanResults:
    """
    Encapsulates scan results with zone/vendor grouping.

    Structure: {zone -> {vendor -> [profiles]}}
    """

    def __init__(self):
        # Nested dict: zone -> vendor -> list of profiles
        self._results: Dict[str, Dict[str, List[ServerProfile]]] = defaultdict(lambda: defaultdict(list))
        self._unknown_zone_profiles: Dict[str, List[ServerProfile]] = defaultdict(list)

    def add_profile(self, profile: ServerProfile):
        """Add a profile to the results"""
        if profile.zone:
            self._results[profile.zone][profile.vendor].append(profile)
        else:
            self._unknown_zone_profiles[profile.vendor].append(profile)

    def get_zones(self) -> List[str]:
        """Get sorted list of zones"""
        return sorted(self._results.keys())

    def get_vendors_in_zone(self, zone: str) -> List[str]:
        """Get sorted list of vendors in a zone"""
        return sorted(self._results.get(zone, {}).keys())

    def get_profiles(self, zone: str, vendor: str) -> List[ServerProfile]:
        """Get profiles for a specific zone and vendor"""
        return self._results.get(zone, {}).get(vendor, [])

    def get_unknown_zone_profiles(self) -> Dict[str, List[ServerProfile]]:
        """Get profiles with unknown zones"""
        return dict(self._unknown_zone_profiles)

    def has_unknown_zone_profiles(self) -> bool:
        """Check if there are profiles with unknown zones"""
        return bool(self._unknown_zone_profiles)

    def get_all_results(self) -> Dict[str, Dict[str, List[ServerProfile]]]:
        """Get the complete nested dictionary"""
        return dict(self._results)

    def total_servers(self) -> int:
        """Get total number of servers"""
        count = 0
        for zone_vendors in self._results.values():
            for profiles in zone_vendors.values():
                count += len(profiles)
        for profiles in self._unknown_zone_profiles.values():
            count += len(profiles)
        return count


class ScannerService:
    """
    Main scanner service - orchestrates the scanning process.

    Design Pattern: Facade Pattern
    Provides a simple interface to complex subsystems (strategies, filters, parsers).
    """

    def __init__(self,
                 oneview_ip: Optional[str] = None,
                 oneview_username: Optional[str] = None,
                 oneview_password: Optional[str] = None,
                 ome_ip: Optional[str] = None,
                 ome_username: Optional[str] = None,
                 ome_password: Optional[str] = None,
                 ucs_central_ip: Optional[str] = None,
                 central_username: Optional[str] = None,
                 central_password: Optional[str] = None,
                 manager_username: Optional[str] = None,
                 manager_password: Optional[str] = None,
                 agent_config: Optional[AgentConfig] = None,
                 zone_config: Optional[ZoneConfig] = None):
        """
        Initialize scanner service.

        Args:
            oneview_ip: HP OneView IP
            oneview_username: HP OneView username
            oneview_password: HP OneView password
            ome_ip: Dell OME IP
            ome_username: Dell OME username
            ome_password: Dell OME password
            ucs_central_ip: Cisco UCS Central IP
            central_username: UCS Central username
            central_password: UCS Central password
            manager_username: UCS Manager username
            manager_password: UCS Manager password
            agent_config: Optional Agent filter configuration
            zone_config: Optional zone filtering configuration
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
        self._agent_filter: Optional[AgentFilter] = None
        self._zone_config = zone_config or ZoneConfig(zones=[])
        self._zone_parser = ZoneParser()

        # Initialize Agent filter if configured
        if agent_config and agent_config.cluster_names:
            try:
                self._agent_filter = AgentFilter(agent_config)
                if self._agent_filter.is_configured():
                    logger.info("Agent filter configured")
                else:
                    logger.warning("Agent filter not properly configured")
                    self._agent_filter = None
            except Exception as e:
                logger.error(f"Failed to initialize Agent filter: {e}")
                self._agent_filter = None

        self._initialize_strategies()

    def _initialize_strategies(self):
        """Initialize vendor strategies for configured vendors"""
        for vendor_type, credentials in self._credentials.items():
            try:
                strategy = StrategyFactory.create_strategy(vendor_type, credentials)
                if strategy.is_configured():
                    self._strategies[vendor_type] = strategy
                    logger.info(f"Initialized strategy for {vendor_type.value}")
            except Exception as e:
                logger.error(f"Error initializing strategy for {vendor_type.value}: {e}")

    def scan(self,
             pattern: str = r"^ocp4-hypershift-.*",
             vendors: Optional[List[str]] = None,
             filter_installed: bool = True) -> ScanResults:
        """
        Scan all configured vendors for server profiles.

        Args:
            pattern: Regex pattern to match server names
            vendors: Optional list of vendors to scan (HP, DELL, CISCO)
            filter_installed: If True, filter out installed servers

        Returns:
            ScanResults object with zone/vendor grouping
        """
        results = ScanResults()

        # Get installed servers if filtering enabled
        installed_servers: Set[str] = set()
        if filter_installed and self._agent_filter:
            try:
                installed_servers = self._agent_filter.get_installed_servers()
                logger.info(f"Found {len(installed_servers)} installed servers to filter out")
            except Exception as e:
                logger.error(f"Error getting installed servers: {e}")

        # Scan each vendor
        for vendor_type, strategy in self._strategies.items():
            # Skip if vendor filter specified and this vendor not in list
            if vendors and vendor_type.value not in [v.upper() for v in vendors]:
                continue

            try:
                profiles = strategy.get_server_profiles(pattern)
                logger.info(f"Found {len(profiles)} profiles in {vendor_type.value}")

                # Filter and enrich profiles
                for profile in profiles:
                    # Skip if installed
                    if filter_installed and profile.name in installed_servers:
                        logger.debug(f"Skipping installed server: {profile.name}")
                        continue

                    # Extract zone
                    zone = self._zone_parser.extract_zone(profile.name)

                    # Apply zone filter
                    if not self._zone_config.is_zone_allowed(zone):
                        logger.debug(f"Skipping server in non-allowed zone: {profile.name} (zone: {zone})")
                        continue

                    # Add zone to profile
                    enriched_profile = profile.with_zone(zone)
                    results.add_profile(enriched_profile)

            except Exception as e:
                logger.error(f"Error scanning {vendor_type.value}: {e}")
            finally:
                strategy.disconnect()

        logger.info(f"Scan complete. Total servers: {results.total_servers()}")
        return results

    def disconnect(self):
        """Disconnect from all systems"""
        for vendor_type, strategy in self._strategies.items():
            try:
                strategy.disconnect()
                strategy.clear_cache()
            except Exception as e:
                logger.warning(f"Error disconnecting from {vendor_type.value}: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def initialize_scanner() -> ScannerService:
    """
    Initialize scanner from environment variables.

    Returns:
        Configured ScannerService instance
    """
    # Vendor credentials
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

    # Agent filter configuration
    agent_config = None
    k8s_cluster_names = os.getenv("K8S_CLUSTER_NAMES")
    k8s_domain_name = os.getenv("K8S_DOMAIN_NAME")
    k8s_token = os.getenv("K8S_TOKEN")

    if k8s_cluster_names and k8s_domain_name and k8s_token:
        agent_config = AgentConfig(
            cluster_names=k8s_cluster_names,
            domain_name=k8s_domain_name,
            token=k8s_token,
            namespace=os.getenv("K8S_NAMESPACE", "assisted-installer")
        )

    # Zone filtering configuration
    zones_str = os.getenv("ZONES")
    zone_config = ZoneConfig.from_string(zones_str)

    scanner = ScannerService(
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
        agent_config=agent_config,
        zone_config=zone_config
    )

    return scanner
