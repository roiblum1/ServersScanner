"""
Pagination abstractions for vendor APIs.

Provides reusable pagination strategies for different vendor API patterns:
- Cursor-based pagination (HP OneView: nextPageUri)
- Offset/limit pagination (Dell OME: $skip/$top)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PaginationStrategy(ABC):
    """Abstract pagination strategy."""

    @abstractmethod
    def get_items(self, page_response: Dict) -> List[Dict[str, Any]]:
        """
        Extract items from page response.

        Args:
            page_response: JSON response from API

        Returns:
            List of items from this page
        """
        pass

    @abstractmethod
    def get_next_url(self, current_url: str, page_response: Dict) -> Optional[str]:
        """
        Get next page URL or None if last page.

        Args:
            current_url: URL of current page
            page_response: JSON response from current page

        Returns:
            URL for next page, or None if no more pages
        """
        pass


class CursorPaginator(PaginationStrategy):
    """
    Cursor-based pagination (HP OneView style).

    Uses a "nextPageUri" field in the response to navigate pages.
    """

    def __init__(self, items_key: str = "members", next_uri_key: str = "nextPageUri"):
        """
        Initialize cursor paginator.

        Args:
            items_key: JSON key containing items array
            next_uri_key: JSON key containing next page URI
        """
        self.items_key = items_key
        self.next_uri_key = next_uri_key

    def get_items(self, page_response: Dict) -> List[Dict]:
        """Extract items from response."""
        return page_response.get(self.items_key, [])

    def get_next_url(self, current_url: str, page_response: Dict) -> Optional[str]:
        """
        Get next page URL from response.

        Handles both relative and absolute URIs.
        """
        next_uri = page_response.get(self.next_uri_key)
        if not next_uri:
            return None

        # If next_uri is relative, construct full URL
        if not next_uri.startswith(('http://', 'https://')):
            # Extract base URL (scheme + host) from current URL
            parts = current_url.split('/')
            if len(parts) >= 3:
                base = '/'.join(parts[:3])  # https://host:port
                next_uri = next_uri.lstrip('/')
                return f"{base}/{next_uri}"

        return next_uri


class OffsetLimitPaginator(PaginationStrategy):
    """
    Offset/limit pagination (Dell OME style).

    Uses $skip and $top query parameters to navigate pages.
    """

    def __init__(self, page_size: int = 100, items_key: str = "value"):
        """
        Initialize offset/limit paginator.

        Args:
            page_size: Number of items per page
            items_key: JSON key containing items array
        """
        self.page_size = page_size
        self.items_key = items_key
        self.current_offset = 0

    def get_items(self, page_response: Dict) -> List[Dict]:
        """Extract items from response."""
        return page_response.get(self.items_key, [])

    def get_next_url(self, current_url: str, page_response: Dict) -> Optional[str]:
        """
        Calculate next page URL based on offset.

        Returns None if current page has fewer items than page_size (last page).
        """
        items = self.get_items(page_response)
        if len(items) < self.page_size:
            return None  # Last page

        self.current_offset += self.page_size

        # Strip existing query params
        base_url = current_url.split('?')[0] if '?' in current_url else current_url

        return f"{base_url}?$skip={self.current_offset}&$top={self.page_size}"


class PaginatedFetcher:
    """
    Generic paginated data fetcher.

    Combines an HTTP client with a pagination strategy to fetch all pages.
    """

    def __init__(self, http_client, paginator: PaginationStrategy):
        """
        Initialize paginated fetcher.

        Args:
            http_client: VendorHTTPClient instance
            paginator: Pagination strategy to use
        """
        self.http_client = http_client
        self.paginator = paginator

    def fetch_all(self, initial_endpoint: str, headers: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Fetch all pages and return combined items.

        Args:
            initial_endpoint: Starting endpoint URL
            headers: Optional HTTP headers

        Returns:
            Combined list of all items from all pages

        Raises:
            requests.HTTPError: For failed requests
        """
        all_items = []
        current_url = initial_endpoint
        page_count = 0

        while current_url:
            page_count += 1
            logger.debug(f"Fetching page {page_count}: {current_url}")

            response = self.http_client.get(current_url, headers=headers)
            page_data = response.json()

            items = self.paginator.get_items(page_data)
            all_items.extend(items)
            logger.debug(f"Page {page_count}: {len(items)} items")

            current_url = self.paginator.get_next_url(current_url, page_data)

        logger.info(f"Fetched {len(all_items)} total items across {page_count} pages")
        return all_items
