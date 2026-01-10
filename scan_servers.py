#!/usr/bin/env python3
"""
Server Inventory Scanner - Refactored with Design Patterns

Queries HP OneView, Dell OME, and Cisco UCS Central for server profiles.
Features:
- Zone-based filtering and grouping
- Kubernetes Agent filtering (filters out installed servers)
- Multiple output formats (list, table, JSON)

Architecture:
- Strategy Pattern for vendor implementations
- Factory Pattern for creating strategies
- Facade Pattern for scanner service
- Value Object Pattern for data models

Usage:
    python scan_servers.py                         # Scan all zones
    python scan_servers.py --zones zone-a,zone-b   # Filter specific zones
    python scan_servers.py --format json           # Output as JSON
    python scan_servers.py --vendor HP             # Scan specific vendor only
    python scan_servers.py --show-all              # Include installed servers
"""

import argparse
import logging
import sys
from dotenv import load_dotenv

from src.services import ScannerService
from src.services.scanner_service import initialize_scanner
from src.formatters import ZoneVendorFormatter


# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Scan HP OneView, Dell OME, and Cisco UCS for server profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan all servers in all zones
  python scan_servers.py

  # Scan specific zones only
  python scan_servers.py --zones zone-a,zone-b

  # Scan only HP servers
  python scan_servers.py --vendor HP

  # Show results as JSON
  python scan_servers.py --format json

  # Include installed servers (don't filter)
  python scan_servers.py --show-all

  # Verbose logging
  python scan_servers.py --verbose
        """
    )

    parser.add_argument(
        "--pattern", "-p",
        default=r"^ocp4-hypershift-.*",
        help="Regex pattern to match server names (default: ^ocp4-hypershift-.*)"
    )

    parser.add_argument(
        "--zones", "-z",
        help="Comma-separated list of zones to include (e.g., zone-a,zone-b). "
             "If not specified, all zones are included. Can also be set via ZONES env var."
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
        help="Output format: list (default), table, or json"
    )

    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON (shortcut for --format json)"
    )

    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all servers including installed ones (default: filter out installed servers)"
    )

    parser.add_argument(
        "--env-file", "-e",
        help="Path to .env file with credentials"
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
        logging.getLogger('urllib3').setLevel(logging.WARNING)  # Suppress urllib3 debug logs

    # Load .env file
    if args.env_file:
        load_dotenv(args.env_file)
        logger.info(f"Loaded environment from {args.env_file}")
    else:
        load_dotenv()  # Load default .env
        logger.info("Loaded environment from .env")

    # Override ZONES if provided via command line
    if args.zones:
        import os
        os.environ["ZONES"] = args.zones
        logger.info(f"Zone filter: {args.zones}")

    print(f"\n🔍 Scanning for servers matching: {args.pattern}\n")

    # Initialize scanner and run scan
    try:
        scanner = initialize_scanner()
    except Exception as e:
        logger.error(f"Failed to initialize scanner: {e}")
        print(f"\n❌ Error initializing scanner: {e}")
        print("\nPlease check your .env configuration and ensure all required credentials are set.")
        sys.exit(1)

    # Perform scan
    filter_installed = not args.show_all
    if args.verbose:
        if filter_installed:
            print("Filter mode: Excluding installed servers (Kubernetes Agent filter active)")
        else:
            print("Filter mode: Including all servers (--show-all)")
        print()

    try:
        results = scanner.scan(
            pattern=args.pattern,
            vendors=args.vendor,
            filter_installed=filter_installed
        )
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        print(f"\n❌ Scan failed: {e}")
        sys.exit(1)

    # Format and display results
    output_format = "json" if args.json else args.format
    formatter = ZoneVendorFormatter(output_format=output_format)

    try:
        output = formatter.format(results)
        print(output)
    except Exception as e:
        logger.error(f"Failed to format output: {e}", exc_info=True)
        print(f"\n❌ Failed to format output: {e}")
        sys.exit(1)

    # Print summary
    if output_format != "json":
        print(f"\n{'=' * 60}")
        print(f"Total servers found: {results.total_servers()}")
        print(f"Zones: {len(results.get_zones())}")
        print(f"{'=' * 60}\n")

    # Cleanup
    scanner.disconnect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScan cancelled by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
