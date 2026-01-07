import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from src.server_strategy import VendorStrategy, ServerProfile

disable_warnings(InsecureRequestWarning)
logger = logging.getLogger(__name__)


class CiscoServerStrategy(VendorStrategy):
    """Cisco UCS Central server profile scanner"""

    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self._ucsc_handle = None
        self._UcsHandle = None

    @property
    def vendor_name(self) -> str:
        return "CISCO"

    def is_configured(self) -> bool:
        """Check if Cisco UCS Central credentials are configured"""
        return all([
            self.credentials.get("central_ip"),
            self.credentials.get("central_username"),
            self.credentials.get("central_password"),
            self.credentials.get("manager_username"),
            self.credentials.get("manager_password")
        ])

    def ensure_connected(self) -> None:
        """Connect to Cisco UCS Central"""
        if self._ucsc_handle:
            return

        central_ip = self.credentials.get('central_ip')
        logger.info(f"Connecting to Cisco UCS Central at {central_ip}...")

        try:
            from ucscsdk.ucschandle import UcscHandle
            from ucsmsdk.ucshandle import UcsHandle

            self._ucsc_handle = UcscHandle(
                central_ip,
                self.credentials['central_username'],
                self.credentials['central_password']
            )
            self._ucsc_handle.login()
            self._UcsHandle = UcsHandle
            logger.info("Successfully connected to Cisco UCS Central")

        except ImportError:
            raise ImportError(
                "Cisco UCS SDK not installed. Run: pip install ucscsdk ucsmsdk"
            )

    def get_server_info(self, server_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get MAC and KVM IP for a SPECIFIC server (used for single server lookup).
        Returns: (mac_address, kvm_ip)
        """
        self.ensure_connected()

        if self._cache is None:
            self._cache = self._ucsc_handle.query_classid("lsServer")

        for server in self._cache:
            if server.name.upper() == server_name.upper():
                domain = server.domain
                logger.info(f"Found server {server_name} in UCS Central, domain: '{domain}'")
                logger.debug(f"Server DN: {server.dn}")

                # Check if domain is empty or None
                if not domain or domain.strip() == "":
                    logger.error(f"Server {server_name} has EMPTY domain value in UCS Central")
                    logger.error(f"Server DN: {server.dn}")
                    logger.error(f"This server is not assigned to a UCS Manager domain or the domain value is not set")
                    logger.error(f"Please check UCS Central configuration and ensure the server is assigned to a domain")
                    return None, None

                ucsm_handle = None

                try:
                    logger.info(f"Connecting to UCS Manager at domain: '{domain}'")
                    ucsm_handle = self._UcsHandle(
                        domain,
                        self.credentials['manager_username'],
                        self.credentials['manager_password']
                    )

                    logger.debug(f"Attempting login to UCS Manager at {domain}...")
                    ucsm_handle.login()
                    logger.info(f"Successfully connected to UCS Manager at {domain}")

                    server_details = self._ucsc_handle.query_dn(server.dn)
                    if not server_details:
                        logger.warning(f"Could not query server details for DN: {server.dn}")
                        continue

                    kvm_ip = self._extract_ucs_management_ip(ucsm_handle, server_details)
                    logger.debug(f"Extracted KVM IP: {kvm_ip}")

                    mac_address = self._extract_ucs_mac_address(ucsm_handle, server_details)
                    logger.debug(f"Extracted MAC address: {mac_address}")

                    if mac_address and kvm_ip:
                        logger.info(f"Successfully retrieved server info for {server_name}: MAC={mac_address}, IP={kvm_ip}")
                        return mac_address, kvm_ip
                    else:
                        logger.warning(f"Incomplete server info for {server_name}: MAC={mac_address}, IP={kvm_ip}")

                except Exception as e:
                    logger.error(f"Error connecting to UCS Manager at {domain}: {type(e).__name__}: {e}")
                    logger.exception("Full UCS Manager connection error:")

                finally:
                    if ucsm_handle:
                        try:
                            ucsm_handle.logout()
                            logger.debug(f"Logged out from UCS Manager at {domain}")
                        except Exception as e:
                            logger.warning(f"Error during UCS Manager logout: {e}")

        return None, None

    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """
        Get all server profiles matching pattern from UCS Central.
        Returns ONLY profile names - no MAC/KVM lookups to avoid wasting API calls.
        """
        self.ensure_connected()

        profiles: List[ServerProfile] = []
        regex = re.compile(pattern, re.IGNORECASE)

        # Query all service profiles from UCS Central - NAMES ONLY
        logger.info("Fetching all service profiles from UCS Central...")
        servers = self._ucsc_handle.query_classid("lsServer")
        logger.info(f"Found {len(servers)} service profiles in UCS Central")

        for server in servers:
            if regex.match(server.name):
                # Just the name - no MAC/KVM lookups
                server_profile = ServerProfile(
                    name=server.name,
                    vendor="CISCO"
                )
                profiles.append(server_profile)

        return profiles

    def _get_domain_server_details(self, domain: str, servers: List) -> Dict[str, Dict]:
        """
        Connect to UCS Manager domain once and fetch details for all servers.
        Returns cache dict: {server_dn: {mac, kvm_ip}}
        """
        details_cache = {}
        ucsm_handle = None

        try:
            # Connect to UCS Manager for this domain
            ucsm_handle = self._UcsHandle(
                domain,
                self.credentials['manager_username'],
                self.credentials['manager_password']
            )
            ucsm_handle.login()
            logger.info(f"Connected to UCS Manager at {domain}")

            # Fetch details for each server (querying children is relatively fast)
            for server in servers:
                try:
                    server_details = self._ucsc_handle.query_dn(server.dn)
                    if not server_details:
                        continue

                    result = {}

                    # Extract KVM IP
                    mgmt_interfaces = ucsm_handle.query_children(
                        in_mo=server_details,
                        class_id="VnicIpV4PooledAddr"
                    )
                    for iface in mgmt_interfaces:
                        if hasattr(iface, "addr") and iface.addr:
                            result["kvm_ip"] = str(iface.addr)
                            break

                    # Extract MAC address
                    adapters = ucsm_handle.query_children(
                        in_mo=server_details,
                        class_id="VnicEther"
                    )
                    if adapters:
                        sorted_adapters = sorted(
                            adapters,
                            key=lambda x: x.name[3:] if len(x.name) > 3 else x.name
                        )
                        if sorted_adapters and hasattr(sorted_adapters[0], "addr"):
                            result["mac"] = sorted_adapters[0].addr

                    if result:
                        details_cache[server.dn] = result

                except Exception as e:
                    logger.debug(f"Could not get details for server {server.name}: {e}")

            logger.info(f"Cached details for {len(details_cache)} servers from domain {domain}")

        except Exception as e:
            logger.error(f"Error connecting to UCS Manager at {domain}: {e}")

        finally:
            if ucsm_handle:
                try:
                    ucsm_handle.logout()
                    logger.debug(f"Disconnected from UCS Manager at {domain}")
                except Exception:
                    pass

        return details_cache

    def _extract_ucs_management_ip(self, ucsm_handle, server_details) -> Optional[str]:
        """Extract KVM IP from server details"""
        try:
            mgmt_interfaces = ucsm_handle.query_children(
                in_mo=server_details,
                class_id="VnicIpV4PooledAddr"
            )

            for iface in mgmt_interfaces:
                if hasattr(iface, "addr") and iface.addr:
                    return str(iface.addr)
        except Exception as e:
            logger.warning(f"Failed to extract UCS management IP: {e}")

        return None

    def _extract_ucs_mac_address(self, ucsm_handle, server_details) -> Optional[str]:
        """Extract MAC address from server details"""
        try:
            adapters = ucsm_handle.query_children(
                in_mo=server_details,
                class_id="VnicEther"
            )

            if adapters:
                # Sort by adapter name (strip first 3 chars if name is long enough, e.g., "eth0" -> "0")
                # Handle short names gracefully
                sorted_adapters = sorted(adapters, key=lambda x: x.name[3:] if len(x.name) > 3 else x.name)
                if sorted_adapters and hasattr(sorted_adapters[0], "addr"):
                    return sorted_adapters[0].addr
        except Exception as e:
            logger.warning(f"Failed to extract UCS MAC address: {e}")

        return None

    def disconnect(self) -> None:
        """Disconnect from Cisco UCS Central"""
        if self._ucsc_handle:
            try:
                self._ucsc_handle.logout()
                logger.info("Successfully disconnected from Cisco UCS Central")
            except Exception as e:
                logger.warning(f"Error during UCS Central logout: {e}")
            finally:
                self._ucsc_handle = None
