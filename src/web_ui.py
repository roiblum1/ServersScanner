"""
FastAPI Web UI for Server Scanner

Provides a web interface to visualize available and installed servers
grouped by zone, vendor, and cluster.

Features:
- In-memory caching with 1-hour TTL
- Automatic background rescan every hour
- Serves cached data for fast responses
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import logging

from src.config import (
    AppConfig,
    VendorConfig,
    KubernetesConfig,
    ZoneConfig,
    FeatureFlags,
    load_environment,
    setup_logging,
    validate_config
)
from src.services.scanner_service import initialize_scanner
from src.models import ServerProfile
from src.filters import AgentFilter

# Logger will be configured later
logger = logging.getLogger(__name__)

# App instance will be created after config is loaded
app = None


# ============================================================================
# Cache Configuration
# ============================================================================

# Use config values (will be initialized from AppConfig)
CACHE_TTL_SECONDS = None
BACKGROUND_SCAN_INTERVAL = None

class CacheEntry:
    """Cache entry with timestamp and data"""
    def __init__(self, data, timestamp: datetime):
        self.data = data
        self.timestamp = timestamp
        self.is_scanning = False

    def is_expired(self) -> bool:
        """Check if cache entry is older than TTL"""
        return datetime.now() - self.timestamp > timedelta(seconds=CACHE_TTL_SECONDS)

    def age_seconds(self) -> int:
        """Get age of cache in seconds"""
        return int((datetime.now() - self.timestamp).total_seconds())


class DataCache:
    """Thread-safe cache for dashboard data"""
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get cached entry if exists and not expired"""
        async with self.lock:
            entry = self.cache.get(key)
            if entry and not entry.is_expired():
                logger.info(f"Cache HIT for key '{key}' (age: {entry.age_seconds()}s)")
                return entry
            elif entry:
                logger.info(f"Cache EXPIRED for key '{key}' (age: {entry.age_seconds()}s)")
            else:
                logger.info(f"Cache MISS for key '{key}'")
            return None

    async def set(self, key: str, data) -> None:
        """Store data in cache with current timestamp"""
        async with self.lock:
            self.cache[key] = CacheEntry(data, datetime.now())
            logger.info(f"Cache SET for key '{key}'")

    async def mark_scanning(self, key: str, scanning: bool) -> None:
        """Mark a cache entry as currently being scanned"""
        async with self.lock:
            entry = self.cache.get(key)
            if entry:
                entry.is_scanning = scanning

    async def is_scanning(self, key: str) -> bool:
        """Check if a scan is in progress for this key"""
        async with self.lock:
            entry = self.cache.get(key)
            return entry.is_scanning if entry else False

    async def clear(self) -> None:
        """Clear all cache"""
        async with self.lock:
            self.cache.clear()
            logger.info("Cache CLEARED")


# Global cache instance
cache = DataCache()


# ============================================================================
# Data Models
# ============================================================================

class ServerInfo(BaseModel):
    """Server information with installation status"""
    name: str
    vendor: str
    zone: Optional[str]
    status: str  # "available" or "installed"
    cluster: Optional[str] = None  # Which cluster it's installed in


class ZoneData(BaseModel):
    """Servers grouped by zone"""
    zone: str
    vendors: Dict[str, List[ServerInfo]]


class ClusterStats(BaseModel):
    """Statistics per cluster"""
    cluster_name: str
    installed_count: int
    servers: List[str]


class CacheInfo(BaseModel):
    """Cache metadata"""
    cached: bool
    age_seconds: int
    next_refresh_seconds: int


class DashboardData(BaseModel):
    """Complete dashboard data"""
    zones: List[ZoneData]
    clusters: List[ClusterStats]
    summary: Dict[str, int]
    cache_info: CacheInfo


# ============================================================================
# Background Tasks
# ============================================================================

async def scan_and_cache(zone_filter: Optional[str] = None) -> DashboardData:
    """
    Perform actual scan and cache the results.

    Args:
        zone_filter: Optional zone filter

    Returns:
        Dashboard data
    """
    cache_key = f"dashboard_{zone_filter or 'all'}"

    # Check if already scanning
    if await cache.is_scanning(cache_key):
        logger.info(f"Scan already in progress for '{cache_key}', skipping")
        return None

    try:
        await cache.mark_scanning(cache_key, True)
        logger.info(f"Starting background scan for '{cache_key}'...")

        # Override zone filter if provided
        if zone_filter:
            os.environ["ZONES"] = zone_filter

        # Initialize scanner
        scanner = initialize_scanner()

        # Get all servers (without filtering installed ones)
        logger.info("Scanning vendors for all servers...")
        all_results = scanner.scan(filter_installed=False)

        # Get installed servers per cluster
        logger.info("Querying Kubernetes for installed servers...")
        installed_by_cluster = get_installed_servers_by_cluster()

        # Build dashboard data
        dashboard_data = build_dashboard_data(all_results, installed_by_cluster)

        # Store in cache
        await cache.set(cache_key, dashboard_data)

        logger.info(f"Background scan completed for '{cache_key}' - cached for {CACHE_TTL_SECONDS}s")
        return dashboard_data

    except Exception as e:
        logger.error(f"Error during background scan: {e}", exc_info=True)
        raise
    finally:
        await cache.mark_scanning(cache_key, False)


async def periodic_rescan():
    """Background task that rescans every hour"""
    logger.info(f"Starting periodic rescan task (interval: {BACKGROUND_SCAN_INTERVAL}s)")

    while True:
        try:
            await asyncio.sleep(BACKGROUND_SCAN_INTERVAL)
            logger.info("Periodic rescan triggered")

            # Rescan default (no filter)
            await scan_and_cache(zone_filter=None)

        except Exception as e:
            logger.error(f"Error in periodic rescan: {e}", exc_info=True)


@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup"""
    logger.info("Application starting up...")

    # Initial scan to populate cache
    logger.info("Performing initial scan...")
    try:
        await scan_and_cache(zone_filter=None)
    except Exception as e:
        logger.error(f"Initial scan failed: {e}")

    # Start periodic rescan task
    asyncio.create_task(periodic_rescan())
    logger.info("Startup complete")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page"""
    return FileResponse("static/html/index.html")


@app.get("/api/servers", response_model=DashboardData)
async def get_servers(
    zone_filter: Optional[str] = None,
    force_refresh: bool = False
):
    """
    Get all servers with their installation status.

    Args:
        zone_filter: Optional comma-separated list of zones to filter
        force_refresh: Force a fresh scan ignoring cache

    Returns:
        Dashboard data with servers grouped by zone and vendor
    """
    cache_key = f"dashboard_{zone_filter or 'all'}"

    try:
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_entry = await cache.get(cache_key)
            if cached_entry:
                # Add cache info
                data = cached_entry.data
                data.cache_info = CacheInfo(
                    cached=True,
                    age_seconds=cached_entry.age_seconds(),
                    next_refresh_seconds=CACHE_TTL_SECONDS - cached_entry.age_seconds()
                )
                return data

        # Cache miss or force refresh - perform scan
        logger.info(f"Performing fresh scan for '{cache_key}'...")
        dashboard_data = await scan_and_cache(zone_filter)

        if dashboard_data:
            dashboard_data.cache_info = CacheInfo(
                cached=False,
                age_seconds=0,
                next_refresh_seconds=CACHE_TTL_SECONDS
            )
            return dashboard_data
        else:
            raise HTTPException(status_code=503, detail="Scan already in progress")

    except Exception as e:
        logger.error(f"Error in get_servers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error scanning servers: {str(e)}")


@app.get("/api/cache/status")
async def get_cache_status():
    """Get cache status for all keys"""
    status = {}
    for key, entry in cache.cache.items():
        status[key] = {
            "age_seconds": entry.age_seconds(),
            "expired": entry.is_expired(),
            "is_scanning": entry.is_scanning,
            "next_refresh_seconds": max(0, CACHE_TTL_SECONDS - entry.age_seconds())
        }
    return {
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "entries": status
    }


@app.post("/api/cache/clear")
async def clear_cache():
    """Manually clear all cache"""
    await cache.clear()
    return {"status": "cache cleared"}


@app.post("/api/scan/trigger")
async def trigger_scan(zone_filter: Optional[str] = None):
    """Manually trigger a background scan"""
    try:
        await scan_and_cache(zone_filter)
        return {"status": "scan completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clusters")
async def get_clusters():
    """Get list of configured clusters"""
    cluster_names = os.getenv("K8S_CLUSTER_NAMES", "").split(",")
    clusters = [name.strip() for name in cluster_names if name.strip()]
    return {"clusters": clusters}


@app.get("/api/zones")
async def get_zones():
    """Get list of discovered zones"""
    try:
        # Try to get from cache first
        cached = await cache.get("dashboard_all")
        if cached:
            zones = [zone.zone for zone in cached.data.zones]
            return {"zones": zones, "cached": True}

        # Fallback to fresh scan
        scanner = initialize_scanner()
        results = scanner.scan(filter_installed=False)
        zones = results.get_zones()
        return {"zones": zones, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting zones: {str(e)}")


# ============================================================================
# Helper Functions
# ============================================================================

def get_installed_servers_by_cluster() -> Dict[str, List[str]]:
    """
    Query Kubernetes to get installed servers per cluster.

    Returns:
        Dict mapping cluster name to list of installed server names
    """
    from src.filters import AgentConfig

    # Get cluster configuration
    cluster_names_str = os.getenv("K8S_CLUSTER_NAMES")
    domain_name = os.getenv("K8S_DOMAIN_NAME")
    token = os.getenv("K8S_TOKEN")
    namespace = os.getenv("K8S_NAMESPACE", "assisted-installer")

    if not all([cluster_names_str, domain_name, token]):
        return {}

    # Create agent filter
    agent_config = AgentConfig(
        cluster_names=cluster_names_str,
        domain_name=domain_name,
        token=token,
        namespace=namespace
    )

    agent_filter = AgentFilter(agent_config)

    # Get installed servers per cluster
    return agent_filter.get_installed_servers_by_cluster()


def build_dashboard_data(all_results, installed_by_cluster: Dict[str, List[str]]) -> DashboardData:
    """
    Build dashboard data structure.

    Args:
        all_results: ScanResults with all servers
        installed_by_cluster: Dict mapping cluster to installed server names

    Returns:
        DashboardData ready for frontend
    """
    # Flatten installed servers to set for quick lookup
    all_installed = set()
    for servers in installed_by_cluster.values():
        all_installed.update(servers)

    # Build zone data
    zones_data = []
    for zone in all_results.get_zones():
        vendors_data = {}

        for vendor in all_results.get_vendors_in_zone(zone):
            profiles = all_results.get_profiles(zone, vendor)
            servers_info = []

            for profile in sorted(profiles, key=lambda p: p.name):
                # Determine status and cluster
                status = "available"
                cluster = None

                if profile.name in all_installed:
                    status = "installed"
                    # Find which cluster
                    for cluster_name, servers in installed_by_cluster.items():
                        if profile.name in servers:
                            cluster = cluster_name
                            break

                servers_info.append(ServerInfo(
                    name=profile.name,
                    vendor=vendor,
                    zone=zone,
                    status=status,
                    cluster=cluster
                ))

            vendors_data[vendor] = servers_info

        zones_data.append(ZoneData(
            zone=zone if zone != "Unknown Zone" else "Unknown",
            vendors=vendors_data
        ))

    # Build cluster stats
    cluster_stats = []
    for cluster_name, servers in installed_by_cluster.items():
        cluster_stats.append(ClusterStats(
            cluster_name=cluster_name,
            installed_count=len(servers),
            servers=sorted(servers)
        ))

    # Build summary
    total_servers = sum(len(servers) for servers in installed_by_cluster.values())
    available_count = sum(
        len([s for s in vendor_servers if s.status == "available"])
        for zone in zones_data
        for vendor_servers in zone.vendors.values()
    )

    summary = {
        "total_available": available_count,
        "total_installed": total_servers,
        "total_clusters": len(installed_by_cluster),
        "total_zones": len(zones_data)
    }

    return DashboardData(
        zones=zones_data,
        clusters=cluster_stats,
        summary=summary,
        cache_info=CacheInfo(
            cached=False,
            age_seconds=0,
            next_refresh_seconds=CACHE_TTL_SECONDS
        )
    )


# ============================================================================
# Initialization
# ============================================================================

def create_app():
    """Create and configure FastAPI application"""
    global app, CACHE_TTL_SECONDS, BACKGROUND_SCAN_INTERVAL

    # Initialize cache settings from config
    CACHE_TTL_SECONDS = AppConfig.CACHE_TTL_SECONDS
    BACKGROUND_SCAN_INTERVAL = AppConfig.BACKGROUND_SCAN_INTERVAL

    # Create FastAPI app
    app = FastAPI(
        title=AppConfig.APP_NAME,
        description=AppConfig.APP_DESCRIPTION,
        version=AppConfig.APP_VERSION
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=AppConfig.STATIC_DIR), name="static")

    return app


# ============================================================================
# Main
# ============================================================================

def main():
    """
    Main entry point with CLI argument support.

    Supports:
        --env-file: Path to .env file
        --verbose: Enable debug logging
        --host: Server host (default: 0.0.0.0)
        --port: Server port (default: 8000)
        --reload: Enable auto-reload (development)
    """
    parser = argparse.ArgumentParser(
        description="Server Scanner Dashboard - Web UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with default .env
  python web_ui.py

  # Use custom .env file
  python web_ui.py --env-file /path/to/custom.env

  # Enable verbose logging
  python web_ui.py --verbose

  # Custom host and port
  python web_ui.py --host 127.0.0.1 --port 9000

  # Development mode with auto-reload
  python web_ui.py --reload --verbose
        """
    )

    parser.add_argument(
        "--env-file", "-e",
        help="Path to .env file with credentials (default: .env)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )

    parser.add_argument(
        "--host",
        default=None,
        help=f"Server host (default: {AppConfig.HOST})"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help=f"Server port (default: {AppConfig.PORT})"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    parser.add_argument(
        "--log-file",
        help="Path to log file (optional)"
    )

    args = parser.parse_args()

    # Load environment
    if args.env_file:
        load_environment(args.env_file)
    # else: already loaded by config module

    # Setup logging
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    # Validate configuration
    try:
        validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Create app
    create_app()

    # Determine host and port
    host = args.host or AppConfig.HOST
    port = args.port or AppConfig.PORT

    # Log startup info
    logger.info(f"Starting {AppConfig.APP_NAME} v{AppConfig.APP_VERSION}")
    logger.info(f"Host: {host}:{port}")
    logger.info(f"Cache TTL: {AppConfig.CACHE_TTL_SECONDS}s")
    logger.info(f"Background scan interval: {AppConfig.BACKGROUND_SCAN_INTERVAL}s")
    logger.info(f"Kubernetes configured: {KubernetesConfig.is_configured()}")

    # Start server
    import uvicorn
    uvicorn.run(
        "src.web_ui:app",
        host=host,
        port=port,
        reload=args.reload or FeatureFlags.RELOAD,
        log_level="debug" if args.verbose else "info"
    )


if __name__ == "__main__":
    main()
