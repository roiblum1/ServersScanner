import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from .base_strategy import VendorStrategy
from ..models import ServerProfile
from ..models.server_document import ServerDocument
from ..parsers import ZoneParser

logger = logging.getLogger(__name__)


class CiscoStrategy(VendorStrategy):
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
                self.credentials['central_password'],
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
                        self.credentials['manager_password'],
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

    def get_full_server_data(
        self,
        pattern: str,
        hardware_details: bool = True,
        batch_size: int = 50,
        batch_delay: float = 1.0,
    ) -> List[ServerDocument]:
        """
        Fetch all matching servers with full hardware details for MongoDB sync.
        Groups servers by UCS Manager domain to minimise connection overhead.
        """
        self.ensure_connected()
        regex = re.compile(pattern, re.IGNORECASE)

        all_servers = self._ucsc_handle.query_classid("lsServer")

        # Group by domain
        by_domain: Dict[str, List] = defaultdict(list)
        for srv in all_servers:
            if regex.match(srv.name):
                by_domain[srv.domain or ""].append(srv)

        docs: List[ServerDocument] = []
        now = datetime.now(timezone.utc)

        # Servers with no domain — record name only
        for srv in by_domain.pop("", []):
            docs.append(ServerDocument(**{
                "_id": srv.name,
                "vendor": "CISCO",
                "zone": ZoneParser.extract_zone(srv.name),
                "last_scanned": now,
            }))

        # Servers per domain
        for domain, domain_servers in by_domain.items():
            ucsm_handle = None
            try:
                ucsm_handle = self._UcsHandle(
                    domain,
                    self.credentials["manager_username"],
                    self.credentials["manager_password"],
                )
                ucsm_handle.login()
                logger.info(f"Cisco: connected to UCS Manager at {domain}")

                for srv in domain_servers:
                    kvm_ip = mac_address = None
                    cpu_model = cpu_count = cpu_cores = memory_gb = model = serial = total_disk_gb = None

                    try:
                        details = self._ucsc_handle.query_dn(srv.dn)
                        if details:
                            kvm_ip = self._extract_ucs_management_ip(ucsm_handle, details)
                            mac_address = self._extract_ucs_mac_address(ucsm_handle, details)

                        hw = self._get_physical_hardware(ucsm_handle, srv)
                        if hw:
                            model = hw.get("model")
                            serial = hw.get("serial")
                            memory_gb = hw.get("memory_gb")
                            cpu_model = hw.get("cpu_model")
                            cpu_count = hw.get("cpu_count")
                            cpu_cores = hw.get("cpu_cores")
                            total_disk_gb = hw.get("total_disk_gb")

                    except Exception as e:
                        logger.warning(f"Cisco: could not get details for '{srv.name}': {e}")

                    docs.append(ServerDocument(**{
                        "_id": srv.name,
                        "vendor": "CISCO",
                        "zone": ZoneParser.extract_zone(srv.name),
                        "bmc_address": kvm_ip,
                        "mac_address": mac_address,
                        "cpu_model": cpu_model,
                        "cpu_count": cpu_count,
                        "cpu_cores": cpu_cores,
                        "memory_gb": memory_gb,
                        "model": model,
                        "serial": serial,
                        "total_disk_gb": total_disk_gb,
                        "last_scanned": now,
                    }))

            except Exception as e:
                logger.error(f"Cisco: error connecting to UCS Manager at {domain}: {e}")
            finally:
                if ucsm_handle:
                    try:
                        ucsm_handle.logout()
                    except Exception:
                        pass

        logger.info(f"Cisco: collected full data for {len(docs)} servers")
        return docs

    def _get_physical_hardware(self, ucsm_handle, srv) -> Optional[Dict]:
        """
        Extract hardware details using the correct UCS SDK object hierarchy:
          srv (lsServer)
            └── pn_dn → ComputeBlade / ComputeRackUnit  (physical server)
                  ├── model, serial, total_memory
                  └── ComputeBoard
                        ├── ProcessorUnit  (CPUs)
                        └── StorageController
                              └── StorageLocalDisk  (disks)
        """
        pn_dn = getattr(srv, "pn_dn", None) or getattr(srv, "pnDn", None)
        if not pn_dn:
            logger.warning(f"Cisco: no physical DN for '{srv.name}'")
            return None

        physical_server = ucsm_handle.query_dn(pn_dn)
        if not physical_server:
            logger.warning(f"Cisco: could not query physical server at DN: {pn_dn}")
            return None

        raw_mem = getattr(physical_server, "total_memory", None)
        hw = {
            "model": getattr(physical_server, "model", None),
            "serial": getattr(physical_server, "serial", None),
            "memory_gb": round(int(raw_mem) / 1024, 1) if raw_mem else None,
            "cpu_model": None,
            "cpu_count": None,
            "cpu_cores": None,
            "total_disk_gb": None,
        }

        # ComputeBoard is the parent of CPUs and storage controllers
        try:
            boards = ucsm_handle.query_children(in_mo=physical_server, class_id="ComputeBoard")
            if not boards:
                logger.warning(f"Cisco: no ComputeBoard found under {pn_dn}")
                return hw
            board = boards[0]
        except Exception as e:
            logger.warning(f"Cisco: failed to get ComputeBoard for '{srv.name}': {e}")
            return hw

        # CPUs: ProcessorUnit children of ComputeBoard
        try:
            cpus = [
                c for c in ucsm_handle.query_children(in_mo=board, class_id="ProcessorUnit")
                if getattr(c, "presence", "") == "equipped"
            ]
            if cpus:
                hw["cpu_model"] = getattr(cpus[0], "model", None)
                raw_cores = getattr(cpus[0], "cores", None)
                hw["cpu_cores"] = int(raw_cores) if raw_cores else None
                hw["cpu_count"] = len(cpus)
        except Exception as e:
            logger.warning(f"Cisco: failed to get CPUs for '{srv.name}': {e}")

        # Disks: StorageController → StorageLocalDisk
        try:
            controllers = ucsm_handle.query_children(in_mo=board, class_id="StorageController")
            size_sum_mb = 0
            for ctrl in controllers:
                for disk in ucsm_handle.query_children(in_mo=ctrl, class_id="StorageLocalDisk"):
                    if getattr(disk, "presence", "") == "equipped":
                        raw_size = getattr(disk, "size", None)
                        size_sum_mb += int(raw_size) if raw_size else 0
            hw["total_disk_gb"] = round(size_sum_mb / 1024, 1) if size_sum_mb else None
        except Exception as e:
            logger.warning(f"Cisco: failed to get disks for '{srv.name}': {e}")

        return hw

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
