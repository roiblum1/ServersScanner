"""
Data models and value objects.
Following Domain-Driven Design patterns for immutable data structures.
"""

from .server_profile import ServerProfile
from .zone_config import ZoneConfig

__all__ = ['ServerProfile', 'ZoneConfig']
