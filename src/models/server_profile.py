"""
Server profile data model - Value Object pattern.
Immutable data structure representing a server profile.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ServerProfile:
    """
    Immutable server profile data.

    Attributes:
        name: Server profile name
        vendor: Vendor type (HP, DELL, CISCO)
        zone: Extracted zone name (e.g., 'zone-a', 'zone-b')
        mac_address: Optional MAC address (only populated when requested)
        bmc_address: Optional BMC/iLO/iDRAC address (only populated when requested)
    """
    name: str
    vendor: str
    zone: Optional[str] = None
    mac_address: Optional[str] = None
    bmc_address: Optional[str] = None

    def __post_init__(self):
        """Validate invariants"""
        if not self.name:
            raise ValueError("Server profile name cannot be empty")
        if not self.vendor:
            raise ValueError("Vendor cannot be empty")

    def with_zone(self, zone: str) -> 'ServerProfile':
        """Create a new instance with zone set (immutable update)"""
        return ServerProfile(
            name=self.name,
            vendor=self.vendor,
            zone=zone,
            mac_address=self.mac_address,
            bmc_address=self.bmc_address
        )

    def with_hardware_info(self, mac: Optional[str], bmc: Optional[str]) -> 'ServerProfile':
        """Create a new instance with hardware info (immutable update)"""
        return ServerProfile(
            name=self.name,
            vendor=self.vendor,
            zone=self.zone,
            mac_address=mac,
            bmc_address=bmc
        )
