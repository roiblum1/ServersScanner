"""
Vendor strategy implementations - Strategy Pattern.
Each vendor (HP, Dell, Cisco) has its own strategy for querying servers.
"""

from .base_strategy import VendorStrategy, VendorType
from .hp_strategy import HPStrategy
from .dell_strategy import DellStrategy
from .cisco_strategy import CiscoStrategy

__all__ = [
    'VendorStrategy',
    'VendorType',
    'HPStrategy',
    'DellStrategy',
    'CiscoStrategy',
]
