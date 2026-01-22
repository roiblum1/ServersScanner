"""
Zone-Vendor formatter - Displays results grouped by zone and vendor.

Output format:
Zone: zone-a
  CISCO:
    - server1
    - server2
  DELL:
    - server3
  HP:
    - server4

Zone: zone-b
  ...
"""

import json
from typing import Dict, List
from .base_formatter import OutputFormatter
from ..services.scanner_service import ScanResults
from ..models import ServerProfile


class ZoneVendorFormatter(OutputFormatter):
    """
    Formatter that groups results by zone, then by vendor.

    Design Pattern: Strategy Pattern implementation
    """

    def __init__(self, output_format: str = "list"):
        """
        Initialize formatter.

        Args:
            output_format: Output format type ('list', 'table', 'json')
        """
        self.output_format = output_format

    def format(self, results: ScanResults) -> str:
        """
        Format scan results with zone/vendor grouping.

        Args:
            results: Scan results

        Returns:
            Formatted output string
        """
        if self.output_format == "json":
            return self._format_json(results)
        elif self.output_format == "table":
            return self._format_table(results)
        else:  # list (default)
            return self._format_list(results)

    def _format_list(self, results: ScanResults) -> str:
        """Format as simple list grouped by zone and vendor"""
        lines = []

        zones = results.get_zones()

        if not zones and not results.has_unknown_zone_profiles():
            return "No servers found matching the pattern."

        for zone in zones:
            lines.append(f"\nZone: {zone}")
            lines.append("=" * 60)

            vendors = results.get_vendors_in_zone(zone)
            for vendor in vendors:
                profiles = results.get_profiles(zone, vendor)
                lines.append(f"\n  {vendor}:")
                for profile in sorted(profiles, key=lambda p: p.name):
                    lines.append(f"    - {profile.name}")

        # Show unknown zone profiles if any
        if results.has_unknown_zone_profiles():
            lines.append(f"\nUnknown Zone:")
            lines.append("=" * 60)

            for vendor, profiles in results.get_unknown_zone_profiles().items():
                lines.append(f"\n  {vendor}:")
                for profile in sorted(profiles, key=lambda p: p.name):
                    lines.append(f"    - {profile.name}")

        return "\n".join(lines)

    def _format_table(self, results: ScanResults) -> str:
        """Format as table with zone/vendor columns"""
        lines = []

        # Header
        lines.append("\n{:<20} {:<10} {:<50}".format("ZONE", "VENDOR", "SERVER NAME"))
        lines.append("=" * 80)

        zones = results.get_zones()

        for zone in zones:
            vendors = results.get_vendors_in_zone(zone)
            for vendor in vendors:
                profiles = results.get_profiles(zone, vendor)
                for i, profile in enumerate(sorted(profiles, key=lambda p: p.name)):
                    # Only show zone on first row for each zone
                    zone_display = zone if i == 0 and vendor == vendors[0] else ""
                    lines.append("{:<20} {:<10} {:<50}".format(
                        zone_display,
                        vendor,
                        profile.name
                    ))

        # Unknown zone profiles
        if results.has_unknown_zone_profiles():
            for vendor, profiles in results.get_unknown_zone_profiles().items():
                for i, profile in enumerate(sorted(profiles, key=lambda p: p.name)):
                    zone_display = "Unknown" if i == 0 else ""
                    lines.append("{:<20} {:<10} {:<50}".format(
                        zone_display,
                        vendor,
                        profile.name
                    ))

        if not zones and not results.has_unknown_zone_profiles():
            lines.append("No servers found matching the pattern.")

        return "\n".join(lines)

    def _format_json(self, results: ScanResults) -> str:
        """Format as JSON with zone/vendor hierarchy"""
        output = {
            "total_servers": results.total_servers(),
            "zones": {}
        }

        # Add zone-grouped results
        for zone in results.get_zones():
            output["zones"][zone] = {}
            for vendor in results.get_vendors_in_zone(zone):
                profiles = results.get_profiles(zone, vendor)
                output["zones"][zone][vendor] = [
                    {"name": p.name, "zone": p.zone, "vendor": p.vendor}
                    for p in sorted(profiles, key=lambda p: p.name)
                ]

        # Add unknown zone profiles
        if results.has_unknown_zone_profiles():
            output["zones"]["unknown"] = {}
            for vendor, profiles in results.get_unknown_zone_profiles().items():
                output["zones"]["unknown"][vendor] = [
                    {"name": p.name, "zone": None, "vendor": p.vendor}
                    for p in sorted(profiles, key=lambda p: p.name)
                ]

        return json.dumps(output, indent=2)
