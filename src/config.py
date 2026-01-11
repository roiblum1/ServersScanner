"""
Centralized Configuration Module

All application constants, logging configuration, and settings.
Import from here instead of hardcoding values.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# ============================================================================
# Load default .env at module import time
# ============================================================================
# This ensures VendorConfig and other classes can access env vars immediately
load_dotenv()

# ============================================================================
# Environment Loading
# ============================================================================

def load_environment(env_file: Optional[str] = None):
    """
    Load environment variables from .env file.

    Args:
        env_file: Optional path to .env file. If None, uses default .env
    """
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path, override=True)
            logging.getLogger(__name__).info(f"Loaded environment from: {env_file}")
        else:
            logging.getLogger(__name__).warning(f"Environment file not found: {env_file}")
    else:
        # Reload default .env
        load_dotenv(override=True)


# ============================================================================
# Application Constants
# ============================================================================

class AppConfig:
    """Application-wide configuration constants"""

    # Application Info
    APP_NAME = "Server Scanner Dashboard"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Monitor available and installed servers across zones, vendors, and clusters"

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    WORKERS = int(os.getenv("WORKERS", "1"))

    # Cache Settings
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour
    BACKGROUND_SCAN_INTERVAL = int(os.getenv("BACKGROUND_SCAN_INTERVAL", "3600"))  # 1 hour

    # API Settings
    API_PREFIX = "/api"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # Static Files
    STATIC_DIR = "static"
    HTML_DIR = "static/html"

    # Default Values
    DEFAULT_ZONE_PATTERN = r"^ocp4-hypershift-.*"
    DEFAULT_OUTPUT_FORMAT = "list"

    # Timeouts
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
    K8S_TIMEOUT = int(os.getenv("K8S_TIMEOUT", "30"))


class VendorConfig:
    """Vendor-specific configuration"""

    # HP OneView
    ONEVIEW_IP = os.getenv("ONEVIEW_IP")
    ONEVIEW_USERNAME = os.getenv("ONEVIEW_USERNAME")
    ONEVIEW_PASSWORD = os.getenv("ONEVIEW_PASSWORD")

    # Dell OME
    OME_IP = os.getenv("OME_IP")
    OME_USERNAME = os.getenv("OME_USERNAME")
    OME_PASSWORD = os.getenv("OME_PASSWORD")

    # Cisco UCS Central
    UCS_CENTRAL_IP = os.getenv("UCS_CENTRAL_IP")
    UCS_CENTRAL_USERNAME = os.getenv("UCS_CENTRAL_USERNAME")
    UCS_CENTRAL_PASSWORD = os.getenv("UCS_CENTRAL_PASSWORD")

    @classmethod
    def get_credentials(cls, vendor: str) -> dict:
        """Get credentials for a specific vendor"""
        vendor_upper = vendor.upper()

        if vendor_upper == "HP":
            return {
                "ip": cls.ONEVIEW_IP,
                "username": cls.ONEVIEW_USERNAME,
                "password": cls.ONEVIEW_PASSWORD
            }
        elif vendor_upper == "DELL":
            return {
                "ip": cls.OME_IP,
                "username": cls.OME_USERNAME,
                "password": cls.OME_PASSWORD
            }
        elif vendor_upper == "CISCO":
            return {
                "ip": cls.UCS_CENTRAL_IP,
                "username": cls.UCS_CENTRAL_USERNAME,
                "password": cls.UCS_CENTRAL_PASSWORD
            }
        else:
            raise ValueError(f"Unknown vendor: {vendor}")


class KubernetesConfig:
    """Kubernetes cluster configuration"""

    CLUSTER_NAMES = os.getenv("K8S_CLUSTER_NAMES", "")
    DOMAIN_NAME = os.getenv("K8S_DOMAIN_NAME", "")
    TOKEN = os.getenv("K8S_TOKEN", "")
    NAMESPACE = os.getenv("K8S_NAMESPACE", "assisted-installer")

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Kubernetes is properly configured"""
        return all([cls.CLUSTER_NAMES, cls.DOMAIN_NAME, cls.TOKEN])

    @classmethod
    def get_cluster_list(cls) -> list:
        """Get list of cluster names"""
        return [c.strip() for c in cls.CLUSTER_NAMES.split(",") if c.strip()]

    @classmethod
    def get_token_list(cls) -> list:
        """Get list of tokens"""
        return [t.strip() for t in cls.TOKEN.split(",") if t.strip()]


class ZoneConfig:
    """Zone filtering configuration"""

    ZONES = os.getenv("ZONES", "")

    @classmethod
    def get_zone_list(cls) -> list:
        """Get list of zones to filter"""
        if not cls.ZONES:
            return []
        return [z.strip() for z in cls.ZONES.split(",") if z.strip()]

    @classmethod
    def is_zone_allowed(cls, zone: Optional[str]) -> bool:
        """Check if a zone is allowed"""
        zones = cls.get_zone_list()
        if not zones:
            return True  # No filter, all zones allowed
        if not zone:
            return True  # Unknown zones always allowed
        return zone in zones


# ============================================================================
# Logging Configuration
# ============================================================================

class LogConfig:
    """Logging configuration"""

    # Log Level
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Log Format
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # Detailed format with file/line
    DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

    # File Logging
    LOG_FILE = os.getenv("LOG_FILE")  # Optional
    LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))  # 10MB
    LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))


def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """
    Configure application logging.

    Args:
        verbose: Enable verbose (DEBUG) logging
        log_file: Optional log file path
    """
    # Determine log level
    if verbose:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, LogConfig.LOG_LEVEL, logging.INFO)

    # Choose format
    log_format = LogConfig.DETAILED_FORMAT if verbose else LogConfig.LOG_FORMAT

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=LogConfig.LOG_DATE_FORMAT
    )

    # Add file handler if specified
    if log_file or LogConfig.LOG_FILE:
        from logging.handlers import RotatingFileHandler

        file_path = log_file or LogConfig.LOG_FILE
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=LogConfig.LOG_FILE_MAX_BYTES,
            backupCount=LogConfig.LOG_FILE_BACKUP_COUNT
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format, LogConfig.LOG_DATE_FORMAT))
        logging.getLogger().addHandler(file_handler)
        logger.info(f"Logging to file: {file_path}")

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("kubernetes").setLevel(logging.WARNING)

    logger.info(f"Logging configured: level={logging.getLevelName(log_level)}")


# Initialize logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# Feature Flags
# ============================================================================

class FeatureFlags:
    """Feature flags for optional functionality"""

    # Enable/disable features
    ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    ENABLE_BACKGROUND_SCAN = os.getenv("ENABLE_BACKGROUND_SCAN", "true").lower() == "true"
    ENABLE_METRICS = os.getenv("ENABLE_METRICS", "false").lower() == "true"
    ENABLE_CORS = os.getenv("ENABLE_CORS", "false").lower() == "true"

    # Development
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    RELOAD = os.getenv("RELOAD", "false").lower() == "true"


# ============================================================================
# Validation
# ============================================================================

def validate_config():
    """
    Validate configuration on startup.
    Raises ValueError if critical configuration is missing.
    """
    errors = []

    # Check vendor credentials (at least one vendor should be configured)
    vendors_configured = 0
    if VendorConfig.ONEVIEW_IP:
        if not all([VendorConfig.ONEVIEW_USERNAME, VendorConfig.ONEVIEW_PASSWORD]):
            errors.append("HP OneView IP configured but missing username/password")
        else:
            vendors_configured += 1

    if VendorConfig.OME_IP:
        if not all([VendorConfig.OME_USERNAME, VendorConfig.OME_PASSWORD]):
            errors.append("Dell OME IP configured but missing username/password")
        else:
            vendors_configured += 1

    if VendorConfig.UCS_CENTRAL_IP:
        if not all([VendorConfig.UCS_CENTRAL_USERNAME, VendorConfig.UCS_CENTRAL_PASSWORD]):
            errors.append("Cisco UCS IP configured but missing username/password")
        else:
            vendors_configured += 1

    if vendors_configured == 0:
        errors.append("No vendor credentials configured (need at least one: HP, Dell, or Cisco)")

    # Warn about Kubernetes (optional)
    if not KubernetesConfig.is_configured():
        logger.warning("Kubernetes not configured - installed server filtering disabled")
    else:
        # Validate token count matches cluster count
        clusters = KubernetesConfig.get_cluster_list()
        tokens = KubernetesConfig.get_token_list()
        if len(tokens) != len(clusters):
            errors.append(f"Token count ({len(tokens)}) doesn't match cluster count ({len(clusters)})")

    # Raise errors if any
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    logger.info(f"Configuration validated: {vendors_configured} vendor(s) configured")


# ============================================================================
# Export commonly used configs
# ============================================================================

# Load environment on module import
load_environment()

# Export for convenience
__all__ = [
    'AppConfig',
    'VendorConfig',
    'KubernetesConfig',
    'ZoneConfig',
    'LogConfig',
    'FeatureFlags',
    'load_environment',
    'setup_logging',
    'validate_config',
]
