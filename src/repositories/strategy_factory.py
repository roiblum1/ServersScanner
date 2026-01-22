"""
Strategy Factory - Factory Pattern implementation.
Creates vendor strategy instances based on vendor type.
"""

import logging
from typing import Dict, Type, Optional

from ..strategies import VendorStrategy, VendorType, HPStrategy, DellStrategy, CiscoStrategy

logger = logging.getLogger(__name__)


class StrategyFactory:
    """
    Factory for creating vendor strategy instances.

    Design Pattern: Factory Pattern + Registry Pattern
    Registers all available strategies and creates instances on demand.
    """

    # Strategy registry
    _STRATEGIES: Dict[VendorType, Type[VendorStrategy]] = {
        VendorType.HP: HPStrategy,
        VendorType.DELL: DellStrategy,
        VendorType.CISCO: CiscoStrategy,
    }

    @classmethod
    def create_strategy(cls, vendor_type: VendorType, credentials: Dict[str, str]) -> VendorStrategy:
        """
        Create a vendor strategy instance.

        Args:
            vendor_type: Type of vendor
            credentials: Vendor-specific credentials

        Returns:
            Initialized strategy instance

        Raises:
            ValueError: If vendor type is not supported
        """
        strategy_class = cls._STRATEGIES.get(vendor_type)

        if not strategy_class:
            raise ValueError(f"Unknown vendor type: {vendor_type}")

        logger.debug(f"Creating strategy for vendor: {vendor_type.value}")
        return strategy_class(credentials)

    @classmethod
    def get_supported_vendors(cls) -> list[VendorType]:
        """
        Get list of supported vendors.

        Returns:
            List of supported VendorType values
        """
        return list(cls._STRATEGIES.keys())

    @classmethod
    def register_strategy(cls, vendor_type: VendorType, strategy_class: Type[VendorStrategy]):
        """
        Register a new strategy (for extensibility).

        Args:
            vendor_type: Vendor type
            strategy_class: Strategy class to register
        """
        cls._STRATEGIES[vendor_type] = strategy_class
        logger.info(f"Registered strategy for vendor: {vendor_type.value}")
