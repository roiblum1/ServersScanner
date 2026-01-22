"""Infrastructure layer for vendor API communication"""
from .http_client import VendorHTTPClient
from .pagination import PaginationStrategy, CursorPaginator, OffsetLimitPaginator, PaginatedFetcher

__all__ = [
    'VendorHTTPClient',
    'PaginationStrategy',
    'CursorPaginator',
    'OffsetLimitPaginator',
    'PaginatedFetcher'
]
