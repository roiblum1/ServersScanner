import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from .base_strategy import VendorStrategy
from ..models import ServerProfile
from ..models.server_document import ServerDocument
from ..parsers import ZoneParser
from ..infrastructure import VendorHTTPClient, OffsetLimitPaginator, PaginatedFetcher

logger = logging.getLogger(__name__)


class DellStrategy(VendorStrategy):
    """Dell OpenManage Enterprise server profile scanner"""

    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.base_url = f"https://{self.credentials.get('ip')}/api" if credentials.get('ip') else None
        self._session_id = None
        self._http_client: Optional[VendorHTTPClient] = None

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
        if self._http_client and self._auth_token:
            return

        logger.info(f"Connecting to Dell OME at {self.credentials.get('ip')}...")

        # Initialize HTTP client
        self._http_client = VendorHTTPClient(
            base_url=self.base_url,
            timeout=30
        )

        # Authenticate
        auth_data = {
            "UserName": self.credentials["username"],
            "Password": self.credentials["password"],
            "SessionType": "API"
        }

        response = self._http_client.post("/SessionService/Sessions", json_data=auth_data)

        self._auth_token = response.headers.get("X-Auth-Token")
        if not self._auth_token:
            raise ValueError("Dell OME did not return X-Auth-Token")

        response_data = response.json()
        self._session_id = response_data.get("Id")

        # Update session headers with auth token
        self._http_client.session.headers.update({"X-Auth-Token": self._auth_token})
        logger.info("Successfully connected to Dell OME")

    def get_server_info(self, server_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get MAC and BMC IP for a SPECIFIC server (used for single server lookup).
        Returns: (mac_address, bmc_ip)
        """
        self.ensure_connected()

        logger.info(f"Searching for Dell server profile: {server_name}")

        # Use paginated fetcher to get all profiles
        paginator = OffsetLimitPaginator(page_size=130, items_key="value")
        fetcher = PaginatedFetcher(self._http_client, paginator)
        all_profiles = fetcher.fetch_all("/ProfileService/Profiles")

        # Search for matching profile
        for server in all_profiles:
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

        logger.error(f"Server profile '{server_name}' not found in Dell OME after checking {len(all_profiles)} profiles.")
        return None, None

    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """
        Scan and return ALL server profiles matching pattern (BULK operation for scanning).
        Returns ONLY profile names - no MAC/BMC lookups to avoid wasting API calls.
        """
        self.ensure_connected()

        profiles: List[ServerProfile] = []
        regex = re.compile(pattern, re.IGNORECASE)

        # Use paginated fetcher to get all profiles
        paginator = OffsetLimitPaginator(page_size=100, items_key="value")
        fetcher = PaginatedFetcher(self._http_client, paginator)
        all_profiles = fetcher.fetch_all("/ProfileService/Profiles")

        # Filter by pattern
        for profile in all_profiles:
            name = profile.get("ProfileName", "")
            if regex.match(name):
                # Just the name - no MAC/BMC lookups
                server_profile = ServerProfile(
                    name=name,
                    vendor="DELL"
                )
                profiles.append(server_profile)

        return profiles

    def get_full_server_data(
        self,
        pattern: str,
        hardware_details: bool = True,
        batch_size: int = 50,
        batch_delay: float = 1.0,
    ) -> List[ServerDocument]:
        """
        Fetch all matching servers for MongoDB sync.

        Bulk calls (always, 0 per-server cost):
          - /ProfileService/Profiles  → profile name + iDRAC IP
          - /DeviceService/Devices    → model, serial (DeviceServiceTag)

        Per-server calls (only when hardware_details=True, 4 calls/server):
          - MAC, CPU, memory, storage inventory
          Batched in groups of `batch_size` with `batch_delay` seconds between
          batches to avoid rate limiting.

        With hardware_details=False: 2 bulk calls total, any server count.
        With hardware_details=True and 1000 servers:
          ~4000 calls spread across ceil(1000/batch_size) batches.
        """
        self.ensure_connected()
        regex = re.compile(pattern, re.IGNORECASE)
        now = datetime.now(timezone.utc)

        # ── 1. Bulk fetch profiles and devices ───────────────────────────
        paginator = OffsetLimitPaginator(page_size=130, items_key="value")
        fetcher = PaginatedFetcher(self._http_client, paginator)
        all_profiles = fetcher.fetch_all("/ProfileService/Profiles")

        dev_paginator = OffsetLimitPaginator(page_size=100, items_key="value")
        dev_fetcher = PaginatedFetcher(self._http_client, dev_paginator)
        all_devices = dev_fetcher.fetch_all("/DeviceService/Devices")
        device_by_ip = {str(d.get("DeviceName", "")): d for d in all_devices}
        logger.info(f"Dell: {len(all_profiles)} profiles, {len(all_devices)} devices (2 bulk calls)")

        # Filter matching profiles
        matching = [
            p for p in all_profiles
            if regex.match(p.get("ProfileName", ""))
        ]
        logger.info(
            f"Dell: {len(matching)} servers match pattern "
            f"({'with' if hardware_details else 'without'} per-server inventory)"
        )

        docs: List[ServerDocument] = []

        for batch_start in range(0, len(matching), batch_size):
            batch = matching[batch_start: batch_start + batch_size]

            for profile in batch:
                name = profile.get("ProfileName", "")
                idrac_ip = profile.get("TargetName")
                device = device_by_ip.get(str(idrac_ip), {}) if idrac_ip else {}
                device_id = device.get("Id")

                mac_address = None
                cpu_model = cpu_count = cpu_cores = memory_gb = total_disk_gb = None

                if hardware_details and device_id:
                    try:
                        mac_address = self._get_device_mac(device_id, name)
                    except Exception as e:
                        logger.warning(f"Dell: failed to get MAC for '{name}': {e}")

                    try:
                        resp = self._http_client.get(
                            f"/DeviceService/Devices({device_id})/InventoryDetails('serverProcessors')"
                        )
                        processors = resp.json().get("InventoryInfo", [])
                        if processors:
                            p = processors[0]
                            cpu_model = p.get("Family") or p.get("ModelName")
                            cpu_count = len(processors)
                            cpu_cores = p.get("NumberOfCores")
                    except Exception as e:
                        logger.warning(f"Dell: failed to get CPU for '{name}': {e}")

                    try:
                        resp = self._http_client.get(
                            f"/DeviceService/Devices({device_id})/InventoryDetails('serverMemoryDevices')"
                        )
                        mem_modules = resp.json().get("InventoryInfo", [])
                        total_mb = sum(m.get("Size", 0) or 0 for m in mem_modules)
                        memory_gb = round(total_mb / 1024, 1) if total_mb else None
                    except Exception as e:
                        logger.warning(f"Dell: failed to get memory for '{name}': {e}")

                    try:
                        resp = self._http_client.get(
                            f"/DeviceService/Devices({device_id})/InventoryDetails('serverStorage')"
                        )
                        size_sum_mb = sum(
                            drv.get("Size") or 0
                            for drv in resp.json().get("InventoryInfo", [])
                        )
                        total_disk_gb = round(size_sum_mb / 1024, 1) if size_sum_mb else None
                    except Exception as e:
                        logger.warning(f"Dell: failed to get storage for '{name}': {e}")

                docs.append(ServerDocument(**{
                    "_id": name,
                    "vendor": "DELL",
                    "zone": ZoneParser.extract_zone(name),
                    "bmc_address": idrac_ip,
                    "mac_address": mac_address,
                    "cpu_model": cpu_model,
                    "cpu_count": cpu_count,
                    "cpu_cores": cpu_cores,
                    "memory_gb": memory_gb,
                    "model": device.get("Model"),
                    "serial": device.get("DeviceServiceTag"),
                    "total_disk_gb": total_disk_gb,
                    "last_scanned": now,
                }))

            # Rate-limit protection: sleep between batches
            if hardware_details and batch_start + batch_size < len(matching):
                logger.debug(
                    f"Dell: batch {batch_start // batch_size + 1} done, "
                    f"sleeping {batch_delay}s before next batch"
                )
                time.sleep(batch_delay)

        logger.info(f"Dell: collected data for {len(docs)} servers")
        return docs

    def _get_dell_mac_address(self, idrac_ip: str, server_name: str) -> Optional[str]:
        """Get MAC address for a specific server by iDRAC IP (used in single server lookup)"""
        self.ensure_connected()

        logger.info(f"Searching for device with iDRAC IP: {idrac_ip}")

        # Use paginated fetcher to get all devices
        paginator = OffsetLimitPaginator(page_size=40, items_key="value")
        fetcher = PaginatedFetcher(self._http_client, paginator)
        all_devices = fetcher.fetch_all("/DeviceService/Devices")

        # Search for device
        device = next((device for device in all_devices if str(device.get("DeviceName")) == str(idrac_ip)), None)

        if device:
            logger.info(f"Found matching device for iDRAC IP: {idrac_ip}")
            device_id = device.get("Id")

            inventory_details_url = f"/DeviceService/Devices({device_id})/InventoryDetails('serverNetworkInterfaces')"
            logger.debug(f"Fetching inventory from URL: {inventory_details_url}")

            response = self._http_client.get(inventory_details_url)
            inventory_details_response = response.json()

            network_interfaces = inventory_details_response.get("InventoryInfo", [])
            logger.debug(f"Network interfaces found: {len(network_interfaces)} for device {device_id}")

            if network_interfaces:
                mac_address = self._extract_mac_by_server_type(network_interfaces, server_name, device_id)
                if mac_address:
                    logger.info(f"MAC address found for server {server_name}: {mac_address}")
                    return mac_address

            logger.error(f"No network interfaces or failed to extract MAC for device {device_id}")
            return None

        logger.error(f"Device with iDRAC IP '{idrac_ip}' not found in Dell OME after checking {len(all_devices)} devices")
        return None

    def _extract_mac_by_server_type(self, network_interfaces: list, server_name: str, device_id: int) -> Optional[str]:
        """
        Extract MAC address based on server type.

        Server types:
        - H100/H200: Uses 3rd network interface (index 2)
        - Data servers: Uses last interface, last port, last partition
        - Default: Uses first interface, first port, first partition
        """
        server_name_lower = server_name.lower()

        try:
            # H100/H200 servers: use 3rd NIC (index 2)
            if "h100" in server_name_lower or "h200" in server_name_lower:
                logger.info(f"Detected H100/H200 server: {server_name}, using 3rd network interface")

                if len(network_interfaces) < 3:
                    logger.error(f"H100/H200 server {server_name} has only {len(network_interfaces)} interfaces, expected at least 3")
                    return None

                third_interface = network_interfaces[2]
                ports = third_interface.get("Ports", [])
                logger.info(f"H100/H200: Found {len(ports)} ports in 3rd interface")

                if not ports:
                    logger.error(f"No ports found in 3rd interface for H100/H200 device {device_id}")
                    return None

                first_port = ports[0]
                partitions = first_port.get("Partitions", [])
                logger.info(f"H100/H200: Found {len(partitions)} partitions in first port")

                if not partitions:
                    logger.error(f"No partitions found in first port of 3rd interface for H100/H200 device {device_id}")
                    return None

                return partitions[0].get("CurrentMacAddress")

            # Data servers: use last interface, last port, last partition
            # Old format: "data" literal in name (e.g. ocp4-hypershift-data-zone-01)
            # New format: "-<N>tb-" storage spec in name (e.g. ocp-dell-r660-site1-128c-1024gb-10tb-ABC123)
            elif "data" in server_name_lower or re.search(r'-\d+tb-', server_name_lower):
                logger.info(f"Using 'data' server logic for {server_name}")
                last_interface = network_interfaces[-1]
                ports = last_interface.get("Ports", [])
                if not ports:
                    logger.error(f"No ports found in last interface for data device {device_id}")
                    return None
                last_port = ports[-1]
                partitions = last_port.get("Partitions", [])
                if not partitions:
                    logger.error(f"No partitions found in last port for data device {device_id}")
                    return None
                return partitions[-1].get("CurrentMacAddress")

            # Default: use first interface, first port, first partition
            else:
                first_interface = network_interfaces[0]
                logger.info(f"Using default logic - First interface: {first_interface}")
                ports = first_interface.get("Ports", [])
                logger.info(f"Ports found: {len(ports)} ports")

                if not ports:
                    logger.error(f"No ports found in first interface for device {device_id}")
                    return None

                first_port = ports[0]
                partitions = first_port.get("Partitions", [])
                logger.info(f"Partitions found: {len(partitions)} partitions")

                if not partitions:
                    logger.error(f"No partitions found in first port for device {device_id}")
                    return None

                return partitions[0].get("CurrentMacAddress")

        except Exception as e:
            logger.error(f"Failed to extract MAC from inventory for device {device_id}: {e}")
            return None

    def _get_device_mac(self, device_id: int, server_name: str) -> Optional[str]:
        """Get MAC address from device inventory (used in bulk scanning)"""
        try:
            url = f"/DeviceService/Devices({device_id})/InventoryDetails('serverNetworkInterfaces')"
            response = self._http_client.get(url)
            interfaces = response.json().get("InventoryInfo", [])
            if interfaces:
                return self._extract_mac_by_server_type(interfaces, server_name, device_id)
        except Exception:
            pass
        return None

    def disconnect(self) -> None:
        """Disconnect from Dell OME"""
        if self._http_client and self._session_id:
            try:
                url = f"/SessionService/Sessions('{self._session_id}')"
                self._http_client.delete(url)
                logger.info("Successfully disconnected from Dell OME")
            except Exception as e:
                logger.warning(f"Error during Dell OME logout: {e}")
            finally:
                self._http_client.close()
                self._http_client = None
                self._auth_token = None
                self._session_id = None
