import logging
import re
from typing import Dict, List, Optional
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

    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """Get all server profiles matching pattern from UCS Central"""
        self.ensure_connected()

        profiles: List[ServerProfile] = []
        regex = re.compile(pattern, re.IGNORECASE)

        # Query all service profiles from UCS Central
        servers = self._ucsc_handle.query_classid("lsServer")

        for server in servers:
            name = server.name

            if regex.match(name):
                server_profile = ServerProfile(
                    name=name,
                    vendor="CISCO",
                    domain=server.domain if server.domain else None
                )

                # Try to get MAC and KVM IP from UCS Manager
                if server.domain and server.domain.strip():
                    try:
                        details = self._get_server_details(server)
                        if details:
                            server_profile.mac_address = details.get("mac")
                            server_profile.bmc_ip = details.get("kvm_ip")
                    except Exception as e:
                        logger.warning(f"Could not get details for {name}: {e}")

                profiles.append(server_profile)

        return profiles

    def _get_server_details(self, server) -> Optional[Dict]:
        """Get MAC and KVM IP by connecting to UCS Manager"""
        domain = server.domain
        if not domain or not domain.strip():
            return None

        ucsm_handle = None
        try:
            ucsm_handle = self._UcsHandle(
                domain,
                self.credentials['manager_username'],
                self.credentials['manager_password']
            )
            ucsm_handle.login()

            server_details = self._ucsc_handle.query_dn(server.dn)
            if not server_details:
                return None

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

            return result if result else None

        except Exception as e:
            logger.debug(f"Error getting server details from UCS Manager: {e}")
            return None
        finally:
            if ucsm_handle:
                try:
                    ucsm_handle.logout()
                except Exception:
                    pass

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
