"""
Zone configuration model.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ZoneConfig:
    """
    Zone filtering configuration.

    Attributes:
        zones: List of zone names to filter (e.g., ['zone-a', 'zone-b'])
        If empty, all zones are included.
    """
    zones: List[str]

    @classmethod
    def from_string(cls, zones_str: Optional[str]) -> 'ZoneConfig':
        """
        Create ZoneConfig from comma-separated string.

        Args:
            zones_str: Comma-separated zone names or None

        Returns:
            ZoneConfig instance
        """
        if not zones_str:
            return cls(zones=[])

        zones = [z.strip() for z in zones_str.split(',') if z.strip()]
        return cls(zones=zones)

    def is_zone_allowed(self, zone: Optional[str]) -> bool:
        """
        Check if a zone is allowed by this configuration.

        Args:
            zone: Zone name to check

        Returns:
            True if zone is allowed (or no zones configured), False otherwise

        Note:
            Servers with unknown zones (zone=None) are ALWAYS allowed,
            regardless of the filter configuration. They will appear in
            an "Unknown Zone" section in the output.
        """
        if not self.zones:  # No filter - all zones allowed
            return True

        if not zone:  # Zone unknown - ALWAYS allow (will show in "Unknown Zone")
            return True

        return zone in self.zones

    def __bool__(self) -> bool:
        """Check if zone filtering is active"""
        return bool(self.zones)
