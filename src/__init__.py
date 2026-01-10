"""
Server Scanner Package

This package provides a unified interface to scan server profiles across
HP OneView, Dell OME, and Cisco UCS Central using industry-standard design patterns.

Architecture:
- Strategy Pattern for vendor implementations
- Factory Pattern for creating strategies
- Facade Pattern for simplified interface
- Value Object Pattern for immutable data models
"""

from .models import ServerProfile, ZoneConfig
from .strategies import VendorStrategy, VendorType, HPStrategy, DellStrategy, CiscoStrategy
from .repositories import StrategyFactory
from .services import ScannerService
from .filters import AgentFilter, AgentConfig
from .formatters import ZoneVendorFormatter

__all__ = [
    # Models
    "ServerProfile",
    "ZoneConfig",
    # Strategies
    "VendorStrategy",
    "VendorType",
    "HPStrategy",
    "DellStrategy",
    "CiscoStrategy",
    # Factory
    "StrategyFactory",
    # Services
    "ScannerService",
    # Filters
    "AgentFilter",
    "AgentConfig",
    # Formatters
    "ZoneVendorFormatter",
]
