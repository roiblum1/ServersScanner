import logging
import re
from typing import Dict, List, Optional, Tuple
import requests
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from src.server_strategy import VendorStrategy, ServerProfile

disable_warnings(InsecureRequestWarning)
logger = logging.getLogger(__name__)


class DellServerStrategy(VendorStrategy):
    """Dell OpenManage Enterprise server profile scanner"""

    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.base_url = f"https://{self.credentials.get('ip')}/api" if credentials.get('ip') else None
        self._session_id = None

    @property
    def vendor_name(self) -> str:
        return "DELL"

    def is_configured(self) -> bool:
        """Check if Dell OME credentials are configured"""
        return all([
            self.credentials.get("ip"),
            self.credentials.get("username"),
            self.credentials.get("password")
        ])

    def ensure_connected(self) -> None:
        """Connect to Dell OME"""
        if self._session and self._auth_token:
            return

        logger.info(f"Connecting to Dell OME at {self.credentials.get('ip')}...")
        self._session = requests.Session()
        self._session.verify = False

        auth_url = f"{self.base_url}/SessionService/Sessions"
        auth_data = {
            "UserName": self.credentials["username"],
            "Password": self.credentials["password"],
            "SessionType": "API"
        }

        response = self._session.post(auth_url, json=auth_data)
        response.raise_for_status()

        self._auth_token = response.headers.get("X-Auth-Token")
        if not self._auth_token:
            raise ValueError("Dell OME did not return X-Auth-Token")

        response_data = response.json()
        self._session_id = response_data.get("Id")

        self._session.headers.update({"X-Auth-Token": self._auth_token})
        logger.info("Successfully connected to Dell OME")

    def get_server_info(self, server_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get MAC and BMC IP for a SPECIFIC server (used for single server lookup).
        Returns: (mac_address, bmc_ip)
        """
        self.ensure_connected()

        device_url = f"{self.base_url}/ProfileService/Profiles"
        skip = 0
        top = 130

        logger.info(f"Searching for Dell server profile: {server_name}")

        while True:
            device_url_with_pagination = f"{device_url}?$skip={skip}&$top={top}"
            response = self._session.get(device_url_with_pagination)
            response.raise_for_status()
            dell_servers_response = response.json()
            dell_servers = dell_servers_response.get("value", [])

            logger.debug(f"Retrieved {len(dell_servers)} profiles (skip={skip}, top={top})")

            for server in dell_servers:
                profile_name = server.get('ProfileName')
                if not profile_name:
                    continue

                logger.debug(f"Checking server profile: {profile_name}")

                if profile_name.upper() == server_name.upper():
                    logger.info(f"Found matching server profile: {profile_name}")
                    idrac_ip = server.get("TargetName")

                    if not idrac_ip:
                        logger.error(f"TargetName (iDRAC IP) is missing for server: {server_name}")
                        return None, None

                    logger.debug(f"iDRAC IP for {server_name}: {idrac_ip}")
                    mac_address = self._get_dell_mac_address(idrac_ip, server_name)

                    if not mac_address:
                        logger.error(f"Failed to retrieve MAC address for server: {server_name}")
                        return None, None

                    logger.info(f"Successfully retrieved server info - MAC: {mac_address}, iDRAC: {idrac_ip}")
                    return mac_address, idrac_ip

            # Check if we've reached the end of pagination
            if len(dell_servers) < top:
                total_checked = skip + len(dell_servers)
                logger.error(f"Server profile '{server_name}' not found in Dell OME after checking {total_checked} profiles.")
                return None, None

            skip += top
            logger.debug(f"No match found in this batch, fetching next {top} profiles...")

    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """
        Scan and return ALL server profiles matching pattern (BULK operation for scanning).
        Returns ONLY profile names - no MAC/BMC lookups to avoid wasting API calls.
        """
        self.ensure_connected()

        profiles: List[ServerProfile] = []
        regex = re.compile(pattern, re.IGNORECASE)

        # Paginate through profiles - NAMES ONLY
        skip = 0
        top = 100

        while True:
            url = f"{self.base_url}/ProfileService/Profiles?$skip={skip}&$top={top}"
            response = self._session.get(url)
            response.raise_for_status()
            data = response.json()

            for profile in data.get("value", []):
                name = profile.get("ProfileName", "")

                if regex.match(name):
                    # Just the name - no MAC/BMC lookups
                    server_profile = ServerProfile(
                        name=name,
                        vendor="DELL"
                    )
                    profiles.append(server_profile)

            if len(data.get("value", [])) < top:
                break
            skip += top

        return profiles

    def _build_device_cache(self) -> Dict[str, Dict]:
        """Build cache of devices by iDRAC IP for quick lookup"""
        logger.info("Fetching all devices from Dell OME...")
        cache = {}
        skip = 0
        top = 100

        # STEP 1: Fetch all devices with basic info
        all_devices = []
        while True:
            url = f"{self.base_url}/DeviceService/Devices?$skip={skip}&$top={top}"
            response = self._session.get(url)
            response.raise_for_status()
            data = response.json()

            devices = data.get("value", [])
            all_devices.extend(devices)

            if len(devices) < top:
                break
            skip += top

        logger.info(f"Found {len(all_devices)} devices in Dell OME")

        # STEP 2: Build cache and fetch MACs (unfortunately Dell requires per-device calls for inventory)
        for device in all_devices:
            device_name = str(device.get("DeviceName", ""))
            device_id = device.get("Id")

            cache[device_name] = {
                "id": device_id,
                "model": device.get("Model"),
                "serial": device.get("DeviceServiceTag")
            }

            # Get MAC address from inventory
            # Note: Dell OME API doesn't support batch inventory queries
            try:
                mac = self._get_device_mac(device_id)
                if mac:
                    cache[device_name]["mac"] = mac
            except Exception as e:
                logger.debug(f"Could not get MAC for device {device_id}: {e}")

        logger.info(f"Cached {len(cache)} device entries with MACs")
        return cache

    def _get_dell_mac_address(self, idrac_ip: str, server_name: str) -> Optional[str]:
        """Get MAC address for a specific server by iDRAC IP (used in single server lookup)"""
        self.ensure_connected()
        device_url = f"{self.base_url}/DeviceService/Devices"
        skip = 0
        top = 40

        logger.info(f"Searching for device with iDRAC IP: {idrac_ip}")

        while True:
            device_url_with_pagination = f"{device_url}?$skip={skip}&$top={top}"
            response = self._session.get(device_url_with_pagination)
            response.raise_for_status()
            devices_response = response.json()

            devices = devices_response.get("value", [])
            logger.debug(f"Retrieved {len(devices)} devices (skip={skip}, top={top})")

            # Search for device in current batch
            device = next((device for device in devices if str(device.get("DeviceName")) == str(idrac_ip)), None)

            if device:
                logger.info(f"Found matching device for iDRAC IP: {idrac_ip}")
                device_id = device.get("Id")

                inventory_details_url = f"{self.base_url}/DeviceService/Devices({device_id})/InventoryDetails('serverNetworkInterfaces')"
                logger.debug(f"Fetching inventory from URL: {inventory_details_url}")

                response = self._session.get(inventory_details_url)
                response.raise_for_status()
                inventory_details_response = response.json()

                network_interfaces = inventory_details_response.get("InventoryInfo", [])
                logger.debug(f"Network interfaces found: {len(network_interfaces)} for device {device_id}")

                if network_interfaces:
                    mac_address = self._extract_mac_from_interfaces(network_interfaces, server_name)
                    if mac_address:
                        logger.info(f"MAC address found for server {server_name}: {mac_address}")
                        return mac_address

                logger.error(f"No network interfaces or failed to extract MAC for device {device_id}")
                return None

            # Check if we've reached the end of pagination
            if len(devices) < top:
                logger.error(f"Device with iDRAC IP '{idrac_ip}' not found in Dell OME after checking {skip + len(devices)} devices")
                break

            skip += top
            logger.debug(f"No match found in this batch, fetching next {top} devices...")

        return None

    def _extract_mac_from_interfaces(self, network_interfaces: list, server_name: str) -> Optional[str]:
        """Extract MAC address from network interfaces (simple first interface logic)"""
        try:
            if network_interfaces:
                first_interface = network_interfaces[0]
                ports = first_interface.get("Ports", [])
                if ports:
                    partitions = ports[0].get("Partitions", [])
                    if partitions:
                        return partitions[0].get("CurrentMacAddress")
        except Exception as e:
            logger.debug(f"Failed to extract MAC from interfaces for {server_name}: {e}")
        return None

    def _get_device_mac(self, device_id: int) -> Optional[str]:
        """Get MAC address from device inventory (used in bulk scanning cache)"""
        try:
            url = f"{self.base_url}/DeviceService/Devices({device_id})/InventoryDetails('serverNetworkInterfaces')"
            response = self._session.get(url)
            response.raise_for_status()
            data = response.json()

            interfaces = data.get("InventoryInfo", [])
            if interfaces:
                first_interface = interfaces[0]
                ports = first_interface.get("Ports", [])
                if ports:
                    partitions = ports[0].get("Partitions", [])
                    if partitions:
                        return partitions[0].get("CurrentMacAddress")
        except Exception:
            pass
        return None

    def disconnect(self) -> None:
        """Disconnect from Dell OME"""
        if self._session and self._session_id:
            try:
                url = f"{self.base_url}/SessionService/Sessions('{self._session_id}')"
                self._session.delete(url)
                logger.info("Successfully disconnected from Dell OME")
            except Exception as e:
                logger.warning(f"Error during Dell OME logout: {e}")
            finally:
                self._session.close()
                self._session = None
                self._auth_token = None
                self._session_id = None
