import logging
import re
from typing import Dict, List, Optional
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

    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """Get all server profiles matching pattern from Dell OME"""
        self.ensure_connected()

        profiles: List[ServerProfile] = []
        regex = re.compile(pattern, re.IGNORECASE)

        # Build device cache for MAC lookup
        device_cache = self._build_device_cache()

        # Paginate through profiles
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
                    idrac_ip = profile.get("TargetName")

                    server_profile = ServerProfile(
                        name=name,
                        vendor="DELL",
                        bmc_ip=idrac_ip
                    )

                    # Try to get MAC from device cache
                    if idrac_ip and idrac_ip in device_cache:
                        device_info = device_cache[idrac_ip]
                        server_profile.mac_address = device_info.get("mac")
                        server_profile.model = device_info.get("model")
                        server_profile.serial_number = device_info.get("serial")

                    profiles.append(server_profile)

            if len(data.get("value", [])) < top:
                break
            skip += top

        return profiles

    def _build_device_cache(self) -> Dict[str, Dict]:
        """Build cache of devices by iDRAC IP for quick lookup"""
        cache = {}
        skip = 0
        top = 100

        while True:
            url = f"{self.base_url}/DeviceService/Devices?$skip={skip}&$top={top}"
            response = self._session.get(url)
            response.raise_for_status()
            data = response.json()

            for device in data.get("value", []):
                device_name = str(device.get("DeviceName", ""))
                device_id = device.get("Id")

                cache[device_name] = {
                    "id": device_id,
                    "model": device.get("Model"),
                    "serial": device.get("DeviceServiceTag")
                }

                # Get MAC address from inventory
                try:
                    mac = self._get_device_mac(device_id)
                    if mac:
                        cache[device_name]["mac"] = mac
                except Exception as e:
                    logger.debug(f"Could not get MAC for device {device_id}: {e}")

            if len(data.get("value", [])) < top:
                break
            skip += top

        return cache

    def _get_device_mac(self, device_id: int) -> Optional[str]:
        """Get MAC address from device inventory"""
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
