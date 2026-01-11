"""
Zone parser for extracting zone names from server profile names.

Examples:
- ocp4-hypershift-zone-a-01 → zone-a
- ocp4-hypershift-data-zone-b-01 → zone-b
- ocp4-hypershift-h100-zone-c-01 → zone-c
- ocp4-hypershift-v100-zone-d-01 → zone-d
- ocp4-hypershift-zone-e-l4-01 → zone-e
"""

import re
from typing import Optional, List


class ZoneParser:
    """
    Parser for extracting zone names from server profile names.

    Handles various patterns:
    - ocp4-hypershift-<zone>-<number>
    - ocp4-hypershift-data-<zone>-<number>
    - ocp4-hypershift-h100-<zone>-<number>
    - ocp4-hypershift-v100-<zone>-<number>
    - ocp4-hypershift-<zone>-l4-<number>
    """

    # Patterns to extract zone (ordered by specificity)
    ZONE_PATTERNS = [
        # Pattern: ocp4-hypershift-data-<zone>-<anything>
        re.compile(r'ocp4-hypershift-data-([a-zA-Z0-9\-]+?)-(?:\d+|l4)', re.IGNORECASE),
        # Pattern: ocp4-hypershift-h100-<zone>-<anything>
        re.compile(r'ocp4-hypershift-h100-([a-zA-Z0-9\-]+?)-(?:\d+|l4)', re.IGNORECASE),
        # Pattern: ocp4-hypershift-v100-<zone>-<anything>
        re.compile(r'ocp4-hypershift-v100-([a-zA-Z0-9\-]+?)-(?:\d+|l4)', re.IGNORECASE),
        # Pattern: ocp4-hypershift-<zone>-<number or l4>
        re.compile(r'ocp4-hypershift-([a-zA-Z0-9\-]+?)-(?:\d+|l4)', re.IGNORECASE),
        # Fallback: anything between ocp4-hypershift- and next hyphen followed by number
        re.compile(r'ocp4-hypershift-([a-zA-Z0-9]+)-', re.IGNORECASE),
    ]

    @classmethod
    def extract_zone(cls, server_name: str) -> Optional[str]:
        """
        Extract zone name from server profile name.

        Args:
            server_name: Server profile name

        Returns:
            Zone name or None if cannot be extracted

        Examples:
            >>> ZoneParser.extract_zone('ocp4-hypershift-zone-a-01')
            'zone-a'
            >>> ZoneParser.extract_zone('ocp4-hypershift-data-zone-b-01')
            'zone-b'
            >>> ZoneParser.extract_zone('ocp4-hypershift-h100-zone-c-01')
            'zone-c'
            >>> ZoneParser.extract_zone('ocp4-hypershift-v100-zone-d-01')
            'zone-d'
            >>> ZoneParser.extract_zone('ocp4-hypershift-zone-e-l4-01')
            'zone-e'
        """
        if not server_name:
            return None

        for pattern in cls.ZONE_PATTERNS:
            match = pattern.search(server_name)
            if match:
                zone = match.group(1)
                # Normalize zone name (lowercase)
                return zone.lower()

        return None

    @classmethod
    def extract_zones_from_list(cls, server_names: List[str]) -> List[str]:
        """
        Extract all unique zones from a list of server names.

        Args:
            server_names: List of server profile names

        Returns:
            Sorted list of unique zone names
        """
        zones = set()
        for name in server_names:
            zone = cls.extract_zone(name)
            if zone:
                zones.add(zone)

        return sorted(zones)

    @classmethod
    def normalize_zone_name(cls, zone: str) -> str:
        """
        Normalize zone name for consistent comparison.

        Args:
            zone: Zone name

        Returns:
            Normalized zone name (lowercase, trimmed)
        """
        return zone.lower().strip()
