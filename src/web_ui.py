#!/usr/bin/env python3
"""
FastAPI Web UI for Server Scanner — MongoDB-backed dashboard.

Architecture:
- API Layer: FastAPI routes (src/api/)
- Service Layer: Business logic (src/services/)
- Storage: MongoDB via Motor (src/storage/database/)
- K8s queries: live at request time (src/repositories/kubernetes_repository.py)

Server data is populated by a daily Kubernetes CronJob (src/cli/sync_mongo.py).
The web app only reads from MongoDB and serves the dashboard.
"""

import argparse
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Fix imports when running as script
if __name__ == "__main__" and __package__ is None:
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    __package__ = "src"

from src.config import (
    AppConfig,
    FeatureFlags,
    KubernetesConfig,
    load_environment,
    setup_logging,
    validate_web_config,
)
from src.api import dashboard_routes, maintenance_routes
from src.api.dependencies import (
    get_mongo_db,
    initialize_dependencies,
)

logger = logging.getLogger(__name__)

app = None


# ============================================================================
# Startup & Shutdown
# ============================================================================

async def startup_event():
    """Connect to MongoDB on app startup."""
    logger.info("Application starting up...")
    mongo_db = get_mongo_db()
    await mongo_db.connect()
    logger.info("MongoDB connected — dashboard ready")


async def shutdown_event():
    """Disconnect from MongoDB on app shutdown."""
    mongo_db = get_mongo_db()
    await mongo_db.disconnect()
    logger.info("MongoDB disconnected — shutdown complete")


# ============================================================================
# Static file route
# ============================================================================

async def read_root():
    """Serve the main HTML page"""
    return FileResponse("static/html/index.html")


# ============================================================================
# Application Factory
# ============================================================================

def create_app():
    """Create and configure the FastAPI application."""
    global app

    initialize_dependencies()

    app = FastAPI(
        title=AppConfig.APP_NAME,
        description=AppConfig.APP_DESCRIPTION,
        version=AppConfig.APP_VERSION,
    )

    app.mount("/static", StaticFiles(directory=AppConfig.STATIC_DIR), name="static")

    app.add_event_handler("startup", startup_event)
    app.add_event_handler("shutdown", shutdown_event)

    app.get("/", response_class=HTMLResponse)(read_root)

    app.include_router(dashboard_routes.router)
    app.include_router(maintenance_routes.router)

    logger.info("Application configured successfully")
    return app


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Server Scanner Dashboard — Web UI")

    parser.add_argument("--env-file", "-e", help="Path to .env file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--host", default=None, help=f"Server host (default: {AppConfig.HOST})")
    parser.add_argument("--port", "-p", type=int, default=None,
                        help=f"Server port (default: {AppConfig.PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev)")
    parser.add_argument("--log-file", help="Path to log file")

    args = parser.parse_args()

    if args.env_file:
        load_environment(args.env_file)

    setup_logging(verbose=args.verbose, log_file=args.log_file)

    try:
        validate_web_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    create_app()

    host = args.host or AppConfig.HOST
    port = args.port or AppConfig.PORT

    logger.info(f"Starting {AppConfig.APP_NAME} v{AppConfig.APP_VERSION}")
    logger.info(f"Host: {host}:{port}")
    logger.info(f"MongoDB: {AppConfig.MONGO_DB_NAME}")
    logger.info(f"Kubernetes configured: {KubernetesConfig.is_configured()}")

    import uvicorn
    uvicorn.run(
        "src.web_ui:app",
        host=host,
        port=port,
        reload=args.reload or FeatureFlags.RELOAD,
        log_level="debug" if args.verbose else "info",
    )


# Initialize app if imported (e.g. by uvicorn directly)
if app is None:
    try:
        load_environment()
        setup_logging()
        validate_web_config()
        app = create_app()
    except Exception as init_error:
        app = FastAPI(title="Server Scanner (Config Error)")
        error_msg = str(init_error)

        @app.get("/")
        async def config_error():
            return {"error": f"Configuration error: {error_msg}"}


if __name__ == "__main__":
    main()
