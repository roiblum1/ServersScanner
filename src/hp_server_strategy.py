import logging
import re
from typing import Dict, List, Optional
import requests
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from src.server_strategy import VendorStrategy, ServerProfile

disable_warnings(InsecureRequestWarning)
logger = logging.getLogger(__name__)


class HPServerStrategy(VendorStrategy):
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

    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """Get all server profiles matching pattern from OneView"""
        self.ensure_connected()

        profiles: List[ServerProfile] = []
        regex = re.compile(pattern, re.IGNORECASE)

        # Paginate through all server profiles
        next_page_uri = f"{self.base_url}/rest/server-profiles?count=-1"

        while next_page_uri:
            response = self._session.get(next_page_uri)
            response.raise_for_status()
            page_data = response.json()

            for profile in page_data.get("members", []):
                name = profile.get("name", "")

                if regex.match(name):
                    server_profile = ServerProfile(
                        name=name,
                        vendor="HP",
                        serial_number=profile.get("serialNumber")
                    )

                    # Try to get hardware details for MAC and iLO IP
                    hardware_uri = profile.get("serverHardwareUri")
                    if hardware_uri:
                        try:
                            hw_details = self._get_hardware_details(hardware_uri)
                            if hw_details:
                                server_profile.mac_address = hw_details.get("mac")
                                server_profile.bmc_ip = hw_details.get("ilo_ip")
                                server_profile.model = hw_details.get("model")
                        except Exception as e:
                            logger.warning(f"Could not get hardware details for {name}: {e}")

                    profiles.append(server_profile)

            next_page_uri = page_data.get("nextPageUri")
            if next_page_uri:
                next_page_uri = f"{self.base_url}{next_page_uri}"

        return profiles

    def _get_hardware_details(self, hardware_uri: str) -> Optional[Dict]:
        """Get hardware details (MAC, iLO IP) from server hardware"""
        if not hardware_uri.startswith("http"):
            hardware_uri = f"{self.base_url}{hardware_uri}"

        response = self._session.get(hardware_uri)
        response.raise_for_status()
        hardware = response.json()

        result = {"model": hardware.get("model")}

        # Extract iLO IP
        if 'mpHostInfo' in hardware and 'mpIpAddresses' in hardware['mpHostInfo']:
            for ip_info in hardware['mpHostInfo']['mpIpAddresses']:
                if ip_info.get('type') == 'Static':
                    result["ilo_ip"] = ip_info.get('address')
                    break

        # Extract MAC address
        port_map = hardware.get("portMap", {})
        for slot in port_map.get("deviceSlots", []):
            for port in slot.get("physicalPorts", []):
                if port.get("type") == "Ethernet":
                    mac = port.get("mac", "")
                    if mac and not mac.startswith('00'):
                        result["mac"] = mac
                        break
            if "mac" in result:
                break

        return result

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
