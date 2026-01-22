#!/usr/bin/env python3
"""
FastAPI Web UI for Server Scanner - Refactored Architecture

Clean separation of concerns with layered architecture:
- API Layer: FastAPI routes (src/api/)
- Service Layer: Business logic (src/services/)
- Repository Layer: Data access (src/repositories/)
- Storage Layer: Persistence (src/storage/)

Features:
- In-memory caching with 1-hour TTL
- Automatic background rescan every hour
- Hybrid caching: vendor scans cached, maintenance status fresh
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

# Fix imports when running as script
if __name__ == "__main__" and __package__ is None:
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    __package__ = "src"

from src.config import (
    AppConfig,
    KubernetesConfig,
    FeatureFlags,
    load_environment,
    setup_logging,
    validate_config
)
from src.api import dashboard_routes, maintenance_routes
from src.api.dependencies import initialize_dependencies, get_cache_repo, get_dashboard_service, get_maintenance_store

logger = logging.getLogger(__name__)

# App instance (created by create_app)
app = None

# Background task interval
BACKGROUND_SCAN_INTERVAL = None


# ============================================================================
# Startup & Background Tasks
# ============================================================================

async def startup_event():
    """Start background tasks on app startup"""
    logger.info("Application starting up...")

    # Initialize maintenance store
    logger.info("Initializing maintenance store...")
    try:
        maintenance_store = get_maintenance_store()
        if maintenance_store:
            await maintenance_store.initialize()
    except Exception as e:
        logger.error(f"Maintenance store initialization failed: {e}")

    # Initial scan to populate cache
    logger.info("Performing initial scan...")
    try:
        cache_repo = get_cache_repo()
        dashboard_service = get_dashboard_service()

        # Check if already scanning
        cache_key = "dashboard_all"
        if not await cache_repo.is_scanning(cache_key):
            try:
                await cache_repo.mark_scanning(cache_key, True)
                dashboard_data = await dashboard_service.build_dashboard(zone_filter=None)
                await cache_repo.set(cache_key, dashboard_data)
                logger.info("Initial scan completed")
            finally:
                await cache_repo.mark_scanning(cache_key, False)
    except Exception as e:
        logger.error(f"Initial scan failed: {e}")

    # Start periodic rescan task
    asyncio.create_task(periodic_rescan())
    logger.info("Startup complete")


async def periodic_rescan():
    """Background task that rescans every hour"""
    logger.info(f"Starting periodic rescan task (interval: {BACKGROUND_SCAN_INTERVAL}s)")

    while True:
        try:
            await asyncio.sleep(BACKGROUND_SCAN_INTERVAL)
            logger.info("Periodic rescan triggered")

            # Rescan default (no filter)
            cache_repo = get_cache_repo()
            dashboard_service = get_dashboard_service()

            cache_key = "dashboard_all"
            if not await cache_repo.is_scanning(cache_key):
                try:
                    await cache_repo.mark_scanning(cache_key, True)
                    dashboard_data = await dashboard_service.build_dashboard(zone_filter=None)
                    await cache_repo.set(cache_key, dashboard_data)
                    logger.info("Periodic rescan completed")
                finally:
                    await cache_repo.mark_scanning(cache_key, False)

        except Exception as e:
            logger.error(f"Error in periodic rescan: {e}", exc_info=True)


# ============================================================================
# Static File Route
# ============================================================================

async def read_root():
    """Serve the main HTML page"""
    return FileResponse("static/html/index.html")


# ============================================================================
# Application Factory
# ============================================================================

def create_app():
    """Create and configure FastAPI application"""
    global app, BACKGROUND_SCAN_INTERVAL

    # Initialize background scan interval
    BACKGROUND_SCAN_INTERVAL = AppConfig.BACKGROUND_SCAN_INTERVAL

    # Initialize dependencies (singleton instances)
    logger.info("Initializing dependencies...")
    initialize_dependencies()

    # Create FastAPI app
    app = FastAPI(
        title=AppConfig.APP_NAME,
        description=AppConfig.APP_DESCRIPTION,
        version=AppConfig.APP_VERSION
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=AppConfig.STATIC_DIR), name="static")

    # Register event handlers
    app.add_event_handler("startup", startup_event)

    # Register static file route
    app.get("/", response_class=HTMLResponse)(read_root)

    # Register API routers
    app.include_router(dashboard_routes.router)
    app.include_router(maintenance_routes.router)

    logger.info("Application configured successfully")
    return app


# ============================================================================
# Main Entry Point
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
    logger.info("Architecture: Layered (API → Service → Repository → Storage)")

    # Start server
    import uvicorn
    uvicorn.run(
        "src.web_ui:app",
        host=host,
        port=port,
        reload=args.reload or FeatureFlags.RELOAD,
        log_level="debug" if args.verbose else "info"
    )


# Initialize app if not running as main (e.g., when imported by uvicorn)
if app is None:
    try:
        load_environment()
        setup_logging()
        validate_config()
        app = create_app()
    except Exception as init_error:
        # If initialization fails, create a minimal app to avoid import errors
        app = FastAPI(title="Server Scanner (Config Error)")
        error_msg = str(init_error)

        @app.get("/")
        async def config_error():
            return {"error": f"Configuration error: {error_msg}"}


if __name__ == "__main__":
    main()
