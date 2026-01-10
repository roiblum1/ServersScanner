"""
Base output formatter - Abstract base class for formatters.
"""

from abc import ABC, abstractmethod
from ..services.scanner_service import ScanResults


class OutputFormatter(ABC):
    """
    Abstract base class for output formatters.

    Design Pattern: Strategy Pattern
    Different formatters for different output styles (list, table, JSON, zone-vendor).
    """

    @abstractmethod
    def format(self, results: ScanResults) -> str:
        """
        Format scan results for output.

        Args:
            results: Scan results to format

        Returns:
            Formatted string for output
        """
        pass
