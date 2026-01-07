#!/usr/bin/env python3
"""
Server Inventory Scanner

Simple script to query HP OneView, Dell OME, and Cisco UCS Central
and list all server profiles matching a pattern (default: ocp4-hypershift-*).

Usage:
    python scan_servers.py                    # Use .env file
    python scan_servers.py --pattern "ocp4-*" # Custom pattern
    python scan_servers.py --json             # Output as JSON
    python scan_servers.py --vendor HP        # Scan specific vendor only
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List

from src.scanner_client import initialize_scanner
from src.server_strategy import ServerProfile


# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def print_list(results: Dict[str, List[ServerProfile]]):
    """Print results as a simple list of names grouped by vendor"""
    all_profiles = []
    for profiles in results.values():
        all_profiles.extend(profiles)

    if not all_profiles:
        print("\nNo servers found matching the pattern.")
        return

    print("\n" + "=" * 80)
    print("SERVER PROFILES")
    print("=" * 80)

    # Print by vendor
    for vendor in sorted(results.keys()):
        profiles = sorted(results[vendor], key=lambda x: x.name)

        if profiles:
            print(f"\n{vendor}:")
            for profile in profiles:
                print(f"  - {profile.name}")

    print("\n" + "=" * 80)

    # Print summary
    print(f"\nSummary:")
    total = 0
    for vendor in sorted(results.keys()):
        count = len(results[vendor])
        total += count
        print(f"  {vendor}: {count} servers")
    print(f"  TOTAL: {total} servers")


def print_table(results: Dict[str, List[ServerProfile]]):
    """Print results as a detailed table"""

    # Calculate column widths
    all_profiles = []
    for profiles in results.values():
        all_profiles.extend(profiles)

    if not all_profiles:
        print("\nNo servers found matching the pattern.")
        return

    # Print header
    print("\n" + "=" * 100)
    print(f"{'SERVER NAME':<40} {'VENDOR':<8} {'BMC IP':<16} {'MAC ADDRESS':<18} {'DOMAIN':<15}")
    print("=" * 100)

    # Print by vendor
    for vendor in sorted(results.keys()):
        profiles = sorted(results[vendor], key=lambda x: x.name)

        if profiles:
            for profile in profiles:
                domain = profile.domain or ""
                bmc_ip = profile.bmc_ip or "-"
                mac = profile.mac_address or "-"

                print(f"{profile.name:<40} {profile.vendor:<8} {bmc_ip:<16} {mac:<18} {domain:<15}")

    print("=" * 100)

    # Print summary
    print(f"\nSummary:")
    total = 0
    for vendor in sorted(results.keys()):
        count = len(results[vendor])
        total += count
        print(f"  {vendor}: {count} servers")
    print(f"  TOTAL: {total} servers")


def print_json(results: Dict[str, List[ServerProfile]]):
    """Print results as JSON"""
    output = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "servers": {}
    }

    for vendor, profiles in results.items():
        output["servers"][vendor] = [p.to_dict() for p in profiles]

    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Scan HP OneView, Dell OME, and Cisco UCS for server profiles"
    )
    parser.add_argument(
        "--pattern", "-p",
        default=r"^ocp4-hypershift-.*",
        help="Regex pattern to match server names (default: ^ocp4-hypershift-.*)"
    )
    parser.add_argument(
        "--vendor", "-v",
        action="append",
        choices=["HP", "DELL", "CISCO"],
        help="Scan specific vendor(s) only (can be repeated)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["list", "table", "json"],
        default="list",
        help="Output format: list (default), table (detailed), or json"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON (shortcut for --format json)"
    )
    parser.add_argument(
        "--env-file", "-e",
        help="Path to .env file with credentials"
    )
    parser.add_argument(
        "--check-duplicates", "-d",
        action="store_true",
        help="Check for duplicate profile names across vendors"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger('src').setLevel(logging.INFO)

    # Load .env file if specified
    if args.env_file:
        try:
            from dotenv import load_dotenv
            load_dotenv(args.env_file)
            print(f"Loaded environment from {args.env_file}")
        except ImportError:
            print("Warning: python-dotenv not installed, cannot load .env file")
            print("Install with: pip install python-dotenv")
            sys.exit(1)

    print(f"\n🔍 Scanning for servers matching: {args.pattern}\n")

    # Initialize scanner and run scan
    scanner = initialize_scanner()
    results = scanner.scan(pattern=args.pattern, vendors=args.vendor)

    # Check for duplicates
    if args.check_duplicates:
        duplicates = scanner.find_duplicates(results)
        if duplicates:
            print(f"\n⚠️  DUPLICATES FOUND across vendors:")
            for name in sorted(duplicates):
                vendors = [v for v, profiles in results.items()
                          if any(p.name == name for p in profiles)]
                print(f"   - {name} exists in: {', '.join(vendors)}")

    # Output results
    output_format = "json" if args.json else args.format

    if output_format == "json":
        print_json(results)
    elif output_format == "table":
        print_table(results)
    else:  # list (default)
        print_list(results)


if __name__ == "__main__":
    main()
