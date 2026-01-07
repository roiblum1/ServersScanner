import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, List, Dict, Type, Tuple
import requests
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)
logger = logging.getLogger(__name__)


@dataclass
class ServerProfile:
    """Represents a server profile from any vendor"""
    name: str
    vendor: str
    mac_address: Optional[str] = None
    bmc_ip: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    domain: Optional[str] = None  # For Cisco - which UCS Manager

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


class VendorType(Enum):
    HP = "HP"
    DELL = "DELL"
    CISCO = "CISCO"


class VendorStrategy(ABC):
    """Abstract base class for vendor strategies"""

    def __init__(self, credentials: Dict[str, str]):
        self.credentials = credentials
        self._cache = None
        self._session = None
        self._auth_token = None

    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Return vendor name"""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if credentials are configured"""
        pass

    @abstractmethod
    def ensure_connected(self) -> None:
        """Ensure connection to the management system"""
        pass

    @abstractmethod
    def get_server_info(self, server_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get MAC and BMC IP for a SPECIFIC server (single server lookup).
        Used by UnifiedServerClient for individual server queries.
        Returns: (mac_address, bmc_ip)
        """
        pass

    @abstractmethod
    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        """
        Get all server profiles matching pattern (BULK scanning operation).
        Used by ServerScanner to list many servers efficiently.
        Returns: List of ServerProfile objects
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the management system"""
        pass

    def clear_cache(self):
        """Clear any cached data."""
        self._cache = None


class VendorStrategyFactory:
    """Factory to create vendor strategy instances"""
    _strategies: Dict[VendorType, Type[VendorStrategy]] = {}

    @classmethod
    def _init_strategies(cls):
        """Lazy initialization of strategies to avoid circular imports"""
        if not cls._strategies:
            from src.hp_server_strategy import HPServerStrategy
            from src.dell_server_strategy import DellServerStrategy
            from src.cisco_server_strategy import CiscoServerStrategy

            cls._strategies = {
                VendorType.HP: HPServerStrategy,
                VendorType.DELL: DellServerStrategy,
                VendorType.CISCO: CiscoServerStrategy,
            }

    @classmethod
    def create_strategy(cls, vendor_type: VendorType, credentials: Dict[str, str]) -> VendorStrategy:
        """Create a strategy instance for the given vendor type"""
        cls._init_strategies()
        strategy_class = cls._strategies.get(vendor_type)
        if not strategy_class:
            raise ValueError(f"No strategy found for vendor type: {vendor_type}")
        return strategy_class(credentials)

    @classmethod
    def register_strategy(cls, vendor_type: VendorType, strategy_class: Type[VendorStrategy]) -> None:
        """Register a custom strategy class"""
        cls._strategies[vendor_type] = strategy_class
