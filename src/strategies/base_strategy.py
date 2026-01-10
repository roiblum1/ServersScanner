"""
Base vendor strategy - Abstract base class using Strategy Pattern.
Defines the interface that all vendor strategies must implement.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Dict, Tuple
import requests
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from ..models import ServerProfile

disable_warnings(InsecureRequestWarning)
logger = logging.getLogger(__name__)


class VendorType(Enum):
    """Vendor enumeration"""
    HP = "HP"
    DELL = "DELL"
    CISCO = "CISCO"


class VendorStrategy(ABC):
    """
    Abstract base class for vendor strategies.

    Design Pattern: Strategy Pattern
    Each vendor implements this interface with vendor-specific logic.

    Responsibilities:
    - Manage connection to vendor management systems
    - Query server profiles
    - Extract hardware information (MAC, BMC)
    """

    def __init__(self, credentials: Dict[str, str]):
        """
        Initialize strategy with credentials.

        Args:
            credentials: Dictionary of vendor-specific credentials
        """
        self.credentials = credentials
        self._cache: Optional[Dict] = None
        self._session: Optional[requests.Session] = None
        self._auth_token: Optional[str] = None

    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Return vendor name"""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if strategy is properly configured with credentials.

        Returns:
            True if all required credentials are present
        """
        pass

    @abstractmethod
    def ensure_connected(self) -> None:
        """
        Ensure connection to vendor management system.
        Authenticate if necessary.
        """
        pass

    @abstractmethod
    def get_server_info(self, server_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get MAC and BMC IP for a specific server.

        This is for single-server detailed lookups (used by other tools).

        Args:
            server_name: Name of the server profile

        Returns:
            Tuple of (mac_address, bmc_ip)
        """
        pass

    @abstractmethod
    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """
        Get all server profiles matching a pattern.

        This is for BULK scanning - returns ONLY names, no MAC/BMC
        (to avoid expensive API calls).

        Args:
            pattern: Regex pattern to match server names

        Returns:
            List of ServerProfile objects (with only name and vendor populated)
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from vendor management system and cleanup resources"""
        pass

    def clear_cache(self):
        """Clear cached data"""
        self._cache = None
