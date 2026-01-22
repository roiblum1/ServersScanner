"""
Base HTTP client for vendor API communication.

Provides common HTTP operations with retry logic, timeout handling,
and session management for all vendor strategies.
"""

from typing import Optional, Dict, Any
from requests import Session, Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)


class VendorHTTPClient:
    """
    Base HTTP client for all vendor APIs with retry and timeout handling.

    Features:
    - Automatic retry for transient failures (429, 500, 502, 503, 504)
    - Configurable timeouts
    - SSL verification control
    - Exponential backoff for retries
    - Safe session cleanup
    """

    def __init__(
        self,
        base_url: str,
        verify_ssl: bool = False,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize HTTP client for vendor API.

        Args:
            base_url: Base URL for API (e.g., "https://oneview.example.com")
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = Session()
        self.session.verify = verify_ssl
        self._setup_retries(max_retries)
        logger.debug(f"Initialized HTTP client for {base_url} (SSL verify: {verify_ssl})")

    def _setup_retries(self, max_retries: int):
        """
        Configure retry strategy for transient failures.

        Args:
            max_retries: Maximum number of retry attempts
        """
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,  # 1s, 2s, 4s, 8s...
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def post(
        self,
        endpoint: str,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Response:
        """
        POST request with automatic error handling.

        Args:
            endpoint: API endpoint (can be relative or absolute URL)
            json_data: JSON payload to send
            headers: Optional HTTP headers
            **kwargs: Additional arguments passed to requests.post()

        Returns:
            Response object

        Raises:
            requests.HTTPError: For failed requests
        """
        url = self._build_url(endpoint)
        response = self.session.post(
            url,
            json=json_data,
            headers=headers,
            timeout=self.timeout,
            **kwargs
        )
        response.raise_for_status()
        return response

    def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Response:
        """
        GET request with automatic error handling.

        Args:
            endpoint: API endpoint (can be relative or absolute URL)
            params: Optional query parameters
            headers: Optional HTTP headers
            **kwargs: Additional arguments passed to requests.get()

        Returns:
            Response object

        Raises:
            requests.HTTPError: For failed requests
        """
        url = self._build_url(endpoint)
        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=self.timeout,
            **kwargs
        )
        response.raise_for_status()
        return response

    def delete(
        self,
        endpoint: str,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Response:
        """
        DELETE request with automatic error handling.

        Args:
            endpoint: API endpoint (can be relative or absolute URL)
            headers: Optional HTTP headers
            **kwargs: Additional arguments passed to requests.delete()

        Returns:
            Response object

        Raises:
            requests.HTTPError: For failed requests
        """
        url = self._build_url(endpoint)
        response = self.session.delete(
            url,
            headers=headers,
            timeout=self.timeout,
            **kwargs
        )
        response.raise_for_status()
        return response

    def _build_url(self, endpoint: str) -> str:
        """
        Build full URL from endpoint.

        Args:
            endpoint: Endpoint path or full URL

        Returns:
            Full URL
        """
        # If endpoint is already a full URL, return as-is
        if endpoint.startswith(('http://', 'https://')):
            return endpoint

        # Otherwise, prepend base URL
        endpoint = endpoint.lstrip('/')
        return f"{self.base_url}/{endpoint}"

    def close(self):
        """Close session safely."""
        if self.session:
            try:
                self.session.close()
                logger.debug("HTTP session closed")
            except Exception as e:
                logger.warning(f"Error closing HTTP session: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()
