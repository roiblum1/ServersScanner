"""
Application-wide and infrastructure configuration.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env at import time (only if file exists — production uses injected env vars)
if Path(".env").exists():
    load_dotenv()


def load_environment(env_file: Optional[str] = None) -> None:
    """Load environment variables from a .env file."""
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path, override=True)
            logging.getLogger(__name__).info(f"Loaded environment from: {env_file}")
        else:
            logging.getLogger(__name__).warning(f"Environment file not found: {env_file}")
    else:
        load_dotenv(override=True)


class AppConfig:
    """Application-wide configuration constants."""

    # Application info
    APP_NAME = "Server Scanner Dashboard"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Monitor available and installed servers across zones, vendors, and clusters"

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    WORKERS = int(os.getenv("WORKERS", "1"))

    # Cache
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    BACKGROUND_SCAN_INTERVAL = int(os.getenv("BACKGROUND_SCAN_INTERVAL", "3600"))

    # API
    API_PREFIX = "/api"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # Static files
    STATIC_DIR = "static"
    HTML_DIR = "static/html"

    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "server_scanner")

    # TLS/SSL — applies to HP, Dell, Cisco, Kubernetes, MongoDB
    TLS_VERIFY = os.getenv("TLS_VERIFY", "false").lower() == "true"

    # CronJob sync rate-limiting (Dell OME)
    SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "50"))
    SYNC_BATCH_DELAY = float(os.getenv("SYNC_BATCH_DELAY", "1.0"))

    # Defaults
    DEFAULT_ZONE_PATTERN = r"^ocp4-hypershift-.*"
    DEFAULT_OUTPUT_FORMAT = "list"

    # Timeouts
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
    K8S_TIMEOUT = int(os.getenv("K8S_TIMEOUT", "30"))


class FeatureFlags:
    """Feature flags for optional functionality."""

    ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    ENABLE_BACKGROUND_SCAN = os.getenv("ENABLE_BACKGROUND_SCAN", "true").lower() == "true"
    ENABLE_METRICS = os.getenv("ENABLE_METRICS", "false").lower() == "true"
    ENABLE_CORS = os.getenv("ENABLE_CORS", "false").lower() == "true"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    RELOAD = os.getenv("RELOAD", "false").lower() == "true"


# Suppress urllib3 InsecureRequestWarning when TLS verification is disabled
if not AppConfig.TLS_VERIFY:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
