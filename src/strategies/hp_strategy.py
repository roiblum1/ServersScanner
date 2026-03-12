import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from .base_strategy import VendorStrategy
from ..models import ServerProfile
from ..models.server_document import ServerDocument
from ..parsers import ZoneParser
from ..infrastructure import VendorHTTPClient, CursorPaginator, PaginatedFetcher

logger = logging.getLogger(__name__)


class HPStrategy(VendorStrategy):
    """HP OneView server profile scanner"""

    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.base_url = f"https://{self.credentials.get('ip')}" if credentials.get('ip') else None
        self._http_client: Optional[VendorHTTPClient] = None

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
        if self._http_client and self._auth_token:
            return

        logger.info(f"Connecting to HP OneView at {self.credentials.get('ip')}...")

        # Initialize HTTP client
        self._http_client = VendorHTTPClient(
            base_url=self.base_url,
            timeout=30
        )

        # Authenticate
        auth_data = {
            "userName": self.credentials["username"],
            "password": self.credentials["password"]
        }
        headers = {"Content-Type": "application/json", "X-API-Version": "2000"}

        response = self._http_client.post("/rest/login-sessions", json_data=auth_data, headers=headers)
        self._auth_token = response.json().get("sessionID")

        # Update session headers with auth token
        self._http_client.session.headers.update({
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
            try:
                # Use paginated fetcher
                paginator = CursorPaginator(items_key="members", next_uri_key="nextPageUri")
                fetcher = PaginatedFetcher(self._http_client, paginator)
                self._cache = fetcher.fetch_all("/rest/server-profiles?count=-1")
            except Exception as e:
                logger.error(f"Failed to retrieve server profiles: {e}")
                return None, None

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

                try:
                    response = self._http_client.get(server_hardware_uri)
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

        # Use paginated fetcher to get all server profiles
        paginator = CursorPaginator(items_key="members", next_uri_key="nextPageUri")
        fetcher = PaginatedFetcher(self._http_client, paginator)
        all_profiles = fetcher.fetch_all("/rest/server-profiles?count=-1")

        # Filter by pattern
        for profile in all_profiles:
            name = profile.get("name", "")
            if regex.match(name):
                # Just the name - no MAC/BMC lookups
                server_profile = ServerProfile(
                    name=name,
                    vendor="HP"
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
        Fetch all matching servers with full hardware details for MongoDB sync.

        Uses TWO bulk API calls regardless of server count:
          1. /rest/server-profiles?count=-1   → all profiles
          2. /rest/server-hardware?count=-1   → all hardware (BMC, MAC, CPU, RAM, disks)

        Then cross-references by serverHardwareUri — zero per-server calls.
        batch_size / batch_delay params are accepted for API compatibility but unused here.
        """
        self.ensure_connected()
        regex = re.compile(pattern, re.IGNORECASE)
        now = datetime.now(timezone.utc)

        # ── 1. Fetch all server profiles (bulk, paginated) ──────────────────
        paginator = CursorPaginator(items_key="members", next_uri_key="nextPageUri")
        fetcher = PaginatedFetcher(self._http_client, paginator)
        all_profiles = fetcher.fetch_all("/rest/server-profiles?count=-1")
        logger.info(f"HP: fetched {len(all_profiles)} server profiles")

        # ── 2. Fetch ALL server hardware in one bulk call ─────────────────
        hw_by_uri: dict = {}
        if hardware_details:
            try:
                all_hw = fetcher.fetch_all("/rest/server-hardware?count=-1")
                hw_by_uri = {hw["uri"]: hw for hw in all_hw if hw.get("uri")}
                logger.info(f"HP: fetched {len(hw_by_uri)} hardware records in bulk (0 per-server calls)")
            except Exception as e:
                logger.warning(f"HP: bulk hardware fetch failed, continuing without hardware details: {e}")

        # ── 3. Cross-reference profiles → hardware ────────────────────────
        docs: List[ServerDocument] = []
        for profile in all_profiles:
            name = profile.get("name", "")
            if not regex.match(name):
                continue

            hw_uri = profile.get("serverHardwareUri", "")
            hardware = hw_by_uri.get(hw_uri, {})
            proc = hardware.get("processorSummary", {})
            mem = hardware.get("memorySummary", {})

            docs.append(ServerDocument(**{
                "_id": name,
                "vendor": "HP",
                "zone": ZoneParser.extract_zone(name),
                "bmc_address": self._extract_ilo_ip(hardware),
                "mac_address": self._extract_mac(hardware),
                "cpu_model": proc.get("model"),
                "cpu_count": proc.get("count"),
                "cpu_cores": proc.get("coreCount"),
                "memory_gb": mem.get("totalSystemMemoryGiB"),
                "model": hardware.get("model"),
                "serial": hardware.get("serialNumber") or profile.get("serialNumber"),
                "disks": self._extract_disks(hardware),
                "last_scanned": now,
            }))

        logger.info(f"HP: collected full data for {len(docs)} servers (2 bulk API calls total)")
        return docs

    def _extract_disks(self, hardware: dict) -> list:
        """Extract local disk info from HP hardware response"""
        disks = []
        storage = hardware.get("localStorage", {})
        for drive in storage.get("drives", []):
            disks.append({
                "size_gb": drive.get("capacityInGB"),
                "type": drive.get("driveMedia"),
                "model": drive.get("model"),
            })
        return disks

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
        if self._http_client and self._auth_token:
            try:
                self._http_client.delete("/rest/login-sessions")
                logger.info("Successfully disconnected from HP OneView")
            except Exception as e:
                logger.warning(f"Error during HP OneView logout: {e}")
            finally:
                self._http_client.close()
                self._http_client = None
                self._auth_token = None
