"""
Startup configuration validation.

Three entry points:
  validate_web_config()  — web dashboard (needs MongoDB)
  validate_sync_config() — CronJob sync (needs MongoDB + at least one vendor)
  validate_config()      — legacy CLI scanner (needs at least one vendor)
"""

import logging
from .app import AppConfig
from .vendors import VendorConfig
from .kubernetes import KubernetesConfig

logger = logging.getLogger(__name__)


def _check_vendor_credentials(errors: list) -> int:
    """Validate all configured vendors and return the count of fully configured ones."""
    configured = 0

    if VendorConfig.ONEVIEW_IP:
        if not all([VendorConfig.ONEVIEW_USERNAME, VendorConfig.ONEVIEW_PASSWORD]):
            errors.append("HP OneView IP configured but missing username/password")
        else:
            configured += 1

    if VendorConfig.OME_IP:
        if not all([VendorConfig.OME_USERNAME, VendorConfig.OME_PASSWORD]):
            errors.append("Dell OME IP configured but missing username/password")
        else:
            configured += 1

    if VendorConfig.UCS_CENTRAL_IP:
        if not all([VendorConfig.UCS_CENTRAL_USERNAME, VendorConfig.UCS_CENTRAL_PASSWORD]):
            errors.append("Cisco UCS IP configured but missing username/password")
        else:
            configured += 1

    return configured


def _check_kubernetes(errors: list) -> None:
    """Warn if K8s is not configured; error if token/cluster count mismatch."""
    if not KubernetesConfig.is_configured():
        logger.warning("Kubernetes not configured - installed server filtering disabled")
        return
    clusters = KubernetesConfig.get_cluster_list()
    tokens = KubernetesConfig.get_token_list()
    if len(tokens) != len(clusters):
        errors.append(f"Token count ({len(tokens)}) doesn't match cluster count ({len(clusters)})")


def _raise_if_errors(errors: list, prefix: str = "Configuration validation failed") -> None:
    if errors:
        raise ValueError(f"{prefix}:\n" + "\n".join(f"  - {e}" for e in errors))


def validate_web_config() -> None:
    """Validate web dashboard configuration (MongoDB required)."""
    errors = []
    if not AppConfig.MONGO_URI:
        errors.append("MONGO_URI is required for the web dashboard")
    _check_kubernetes(errors)
    _raise_if_errors(errors)
    logger.info(f"Web config validated: MongoDB='{AppConfig.MONGO_DB_NAME}'")


def validate_sync_config() -> None:
    """Validate CronJob sync configuration (MongoDB + at least one vendor required)."""
    errors = []
    if not AppConfig.MONGO_URI:
        errors.append("MONGO_URI is required for the sync job")
    n = _check_vendor_credentials(errors)
    if n == 0:
        errors.append("No vendor credentials configured (need at least one: HP, Dell, or Cisco)")
    _raise_if_errors(errors, "Sync config validation failed")
    logger.info(f"Sync config validated: {n} vendor(s), MongoDB='{AppConfig.MONGO_DB_NAME}'")


def validate_config() -> None:
    """Validate legacy CLI scanner configuration (at least one vendor required)."""
    errors = []
    n = _check_vendor_credentials(errors)
    if n == 0:
        errors.append("No vendor credentials configured (need at least one: HP, Dell, or Cisco)")
    _check_kubernetes(errors)
    _raise_if_errors(errors)
    logger.info(f"Configuration validated: {n} vendor(s) configured")
