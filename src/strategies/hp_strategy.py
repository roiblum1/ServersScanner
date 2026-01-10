import logging
import re
from typing import Dict, List, Optional, Tuple
import requests
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from .base_strategy import VendorStrategy
from ..models import ServerProfile

disable_warnings(InsecureRequestWarning)
logger = logging.getLogger(__name__)


class HPStrategy(VendorStrategy):
    """HP OneView server profile scanner"""

    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.base_url = f"https://{self.credentials.get('ip')}" if credentials.get('ip') else None

    @property
    def vendor_name(self) -> str:
        return "HP"

    def is_configured(self) -> bool:
        """Check if HP OneView credentials are configured"""
        return all([
            self.credentials.get("ip"),
            self.credentials.get("username"),
            self.credentials.get("password")
        ])

    def ensure_connected(self) -> None:
        """Connect to HP OneView"""
        if self._session and self._auth_token:
            return

        logger.info(f"Connecting to HP OneView at {self.credentials.get('ip')}...")
        self._session = requests.Session()
        self._session.verify = False

        auth_url = f"{self.base_url}/rest/login-sessions"
        auth_data = {
            "userName": self.credentials["username"],
            "password": self.credentials["password"]
        }
        headers = {"Content-Type": "application/json", "X-API-Version": "2000"}

        response = self._session.post(auth_url, json=auth_data, headers=headers)
        response.raise_for_status()

        self._auth_token = response.json().get("sessionID")
        self._session.headers.update({
            "Auth": self._auth_token,
            "X-API-Version": "2000"
        })
        logger.info("Successfully connected to HP OneView")

    def get_server_info(self, server_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get MAC and BMC IP for a SPECIFIC server (used for single server lookup).
        Returns: (mac_address, bmc_ip)
        """
        self.ensure_connected()

        # Build cache if not exists
        if self._cache is None:
            self._cache = []
            next_page_uri = f"{self.base_url}/rest/server-profiles?count=-1"

            while next_page_uri:
                try:
                    response = self._session.get(next_page_uri)
                    response.raise_for_status()
                    page_data = response.json()
                except Exception as e:
                    logger.error(f"Failed to retrieve server profiles: {e}")
                    return None, None

                self._cache.extend(page_data.get("members", []))
                next_page_uri = page_data.get("nextPageUri")
                if next_page_uri:
                    next_page_uri = f"{self.base_url}{next_page_uri}"

        # Find specific server
        for server in self._cache:
            server_name_attr = server.get("name")
            server_serial_number = server.get("serialNumber")

            if (server_name and server_name_attr and server_name.upper() == server_name_attr.upper()) or \
               (server_name and server_serial_number and server_name.upper() == server_serial_number.upper()):
                server_hardware_uri = server.get("serverHardwareUri")
                if not server_hardware_uri:
                    logger.warning(f"Server {server_name} has no serverHardwareUri")
                    continue

                if not server_hardware_uri.startswith(self.base_url):
                    server_hardware_uri = f"{self.base_url}{server_hardware_uri}"

                try:
                    response = self._session.get(server_hardware_uri)
                    response.raise_for_status()
                    server_hardware = response.json()
                except Exception as e:
                    logger.error(f"Failed to retrieve server hardware details: {e}")
                    return None, None

                ilo_ip = self._extract_ilo_ip(server_hardware)
                if not ilo_ip:
                    logger.error(f"Could not find iLO IP address for server {server_name}")
                    return None, None

                mac_address = self._extract_mac(server_hardware)
                if not mac_address:
                    logger.error(f"Could not find MAC address for server {server_name}")
                    return None, None

                if mac_address and ilo_ip:
                    return mac_address, ilo_ip

        logger.error(f"Server {server_name} not found in OneView")
        return None, None

    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """
        Scan and return ALL server profiles matching pattern (BULK operation for scanning).
        Returns ONLY profile names - no MAC/BMC lookups to avoid wasting API calls.
        """
        self.ensure_connected()

        profiles: List[ServerProfile] = []
        regex = re.compile(pattern, re.IGNORECASE)

        # Paginate through all server profiles - NAMES ONLY
        next_page_uri = f"{self.base_url}/rest/server-profiles?count=-1"

        while next_page_uri:
            response = self._session.get(next_page_uri)
            response.raise_for_status()
            page_data = response.json()

            for profile in page_data.get("members", []):
                name = profile.get("name", "")

                if regex.match(name):
                    # Just the name - no MAC/BMC lookups
                    server_profile = ServerProfile(
                        name=name,
                        vendor="HP"
                    )
                    profiles.append(server_profile)

            next_page_uri = page_data.get("nextPageUri")
            if next_page_uri:
                next_page_uri = f"{self.base_url}{next_page_uri}"

        return profiles

    def _extract_ilo_ip(self, hardware: dict) -> Optional[str]:
        """Extract iLO IP from hardware data"""
        if 'mpHostInfo' in hardware and 'mpIpAddresses' in hardware['mpHostInfo']:
            for ip_info in hardware['mpHostInfo']['mpIpAddresses']:
                if ip_info.get('type') == 'Static':
                    return ip_info.get('address')
        return None

    def _extract_mac(self, hardware: dict) -> Optional[str]:
        """Extract MAC address from hardware data"""
        port_map = hardware.get("portMap", {})
        for slot in port_map.get("deviceSlots", []):
            for port in slot.get("physicalPorts", []):
                if port.get("type") == "Ethernet":
                    mac = port.get("mac", "")
                    if mac and not mac.startswith('00'):
                        return mac
        return None

    def disconnect(self) -> None:
        """Disconnect from HP OneView"""
        if self._session and self._auth_token:
            try:
                self._session.delete(f"{self.base_url}/rest/login-sessions")
                logger.info("Successfully disconnected from HP OneView")
            except Exception as e:
                logger.warning(f"Error during HP OneView logout: {e}")
            finally:
                self._session.close()
                self._session = None
                self._auth_token = None
