"""
Configuration shim — re-exports everything from src/configuration/.

All imports of the form `from ..config import AppConfig` continue to work.
Add new config to the appropriate module inside src/configuration/.
"""

from .configuration import (
    AppConfig,
    FeatureFlags,
    load_environment,
    VendorConfig,
    KubernetesConfig,
    LogConfig,
    setup_logging,
    validate_config,
    validate_web_config,
    validate_sync_config,
)

# ZoneConfig (class-based zone filter, used by the legacy CLI scanner)
import os
from typing import Optional


class ZoneConfig:
    """Zone filtering configuration (legacy CLI)."""

    ZONES = os.getenv("ZONES", "")

    @classmethod
    def get_zone_list(cls) -> list:
        if not cls.ZONES:
            return []
        return [z.strip() for z in cls.ZONES.split(",") if z.strip()]

    @classmethod
    def is_zone_allowed(cls, zone: Optional[str]) -> bool:
        zones = cls.get_zone_list()
        if not zones:
            return True
        if not zone:
            return True
        return zone in zones


__all__ = [
    "AppConfig",
    "VendorConfig",
    "KubernetesConfig",
    "ZoneConfig",
    "LogConfig",
    "FeatureFlags",
    "load_environment",
    "setup_logging",
    "validate_config",
    "validate_web_config",
    "validate_sync_config",
]
