"""
Hostname parser for extracting server names from Kubernetes Agent resources.

Logic:
1. Try to use `hostname` field
2. If `hostname` is a MAC address, use `requestedHostname` instead
3. Only consider hosts matching the pattern (ocp4-hypershift-*)
"""

import re
from typing import Optional


class HostnameParser:
    """
    Parser for extracting valid hostnames from Kubernetes Agent resources.

    Implements the business logic:
    - hostname is preferred
    - If hostname is MAC address, fall back to requestedHostname
    - Only accept names matching ocp4-hypershift pattern
    """

    # MAC address pattern (various formats)
    MAC_PATTERN = re.compile(
        r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$|^([0-9A-Fa-f]{12})$'
    )

    # Server name pattern
    SERVER_NAME_PATTERN = re.compile(r'ocp4-hypershift', re.IGNORECASE)

    @classmethod
    def is_mac_address(cls, value: str) -> bool:
        """
        Check if a string is a MAC address.

        Args:
            value: String to check

        Returns:
            True if value is a MAC address
        """
        if not value:
            return False
        return bool(cls.MAC_PATTERN.match(value.strip()))

    @classmethod
    def is_valid_server_name(cls, name: Optional[str]) -> bool:
        """
        Check if a server name matches the required pattern.

        Args:
            name: Server name to validate

        Returns:
            True if name contains 'ocp4-hypershift'
        """
        if not name:
            return False
        return bool(cls.SERVER_NAME_PATTERN.search(name))

    @classmethod
    def extract_hostname(cls, hostname: Optional[str], requested_hostname: Optional[str]) -> Optional[str]:
        """
        Extract the actual server name from Agent hostname fields.

        Logic:
        1. If hostname is valid (not MAC and matches pattern), use it
        2. If hostname is MAC address, try requestedHostname
        3. If requestedHostname matches pattern, use it
        4. Otherwise, return None

        Args:
            hostname: The 'hostname' field from Agent
            requested_hostname: The 'requestedHostname' field from Agent

        Returns:
            Extracted server name or None if no valid name found
        """
        # Try hostname first
        if hostname and not cls.is_mac_address(hostname):
            if cls.is_valid_server_name(hostname):
                return hostname

        # If hostname is MAC or invalid, try requestedHostname
        if hostname and cls.is_mac_address(hostname):
            if requested_hostname and cls.is_valid_server_name(requested_hostname):
                return requested_hostname

        # Last resort: check if requestedHostname is valid even if hostname wasn't MAC
        if requested_hostname and cls.is_valid_server_name(requested_hostname):
            return requested_hostname

        return None
