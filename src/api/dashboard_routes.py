"""
Dashboard API routes for server scanning and monitoring.

Provides endpoints for retrieving server data, cache management,
and system status.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from ..models.api_responses import (
    DashboardData,
    StatusResponse,
    CacheStatusResponse,
    CacheEntryStatus
)
from ..repositories import CacheRepository
from ..services.dashboard_service import DashboardService
from .dependencies import get_cache_repo, get_dashboard_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/api/servers", response_model=DashboardData)
async def get_servers(
    zone_filter: Optional[str] = None,
    force_refresh: bool = False,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(500, ge=10, le=2000, description="Servers per page"),
    cache_repo: CacheRepository = Depends(get_cache_repo),
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """
    Get all servers with their installation status.

    Args:
        zone_filter: Optional comma-separated list of zones to filter
        force_refresh: Force a fresh scan ignoring cache
        page: Page number (1-based)
        page_size: Number of servers per page (10–2000, default 500)

    Returns:
        Dashboard data with servers grouped by zone and vendor
    """
    cache_key = f"dashboard_{zone_filter or 'all'}_{page}_{page_size}"

    try:
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_entry = await cache_repo.get(cache_key)
            if cached_entry:
                data = cached_entry.data
                data.cache_info.cached = True
                data.cache_info.age_seconds = cached_entry.age_seconds()
                data.cache_info.next_refresh_seconds = cache_repo.ttl_seconds - cached_entry.age_seconds()
                logger.info(f"Returning cached dashboard (age: {data.cache_info.age_seconds}s)")
                return data

        # Cache miss or force refresh - perform scan
        logger.info(f"Performing fresh scan for '{cache_key}'...")

        # Check if already scanning
        if await cache_repo.is_scanning(cache_key):
            logger.info(f"Scan already in progress for '{cache_key}'")
            raise HTTPException(status_code=503, detail="Scan already in progress")

        try:
            await cache_repo.mark_scanning(cache_key, True)

            # Perform scan
            dashboard_data = await dashboard_service.build_dashboard(zone_filter, page, page_size)

            # Store in cache
            await cache_repo.set(cache_key, dashboard_data)

            dashboard_data.cache_info.cached = False
            dashboard_data.cache_info.age_seconds = 0
            dashboard_data.cache_info.next_refresh_seconds = cache_repo.ttl_seconds

            return dashboard_data

        finally:
            await cache_repo.mark_scanning(cache_key, False)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_servers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error scanning servers: {str(e)}")


@router.get("/api/cache/status", response_model=CacheStatusResponse)
async def get_cache_status(
    cache_repo: CacheRepository = Depends(get_cache_repo)
):
    """
    Get cache status for all keys.

    Returns:
        Status of all cache entries with age and expiration info
    """
    entries_status = cache_repo.get_all_status()

    # Convert to Pydantic models
    entries = {
        key: CacheEntryStatus(**status)
        for key, status in entries_status.items()
    }

    return CacheStatusResponse(
        cache_ttl_seconds=cache_repo.ttl_seconds,
        entries=entries
    )


@router.post("/api/cache/clear", response_model=StatusResponse)
async def clear_cache(
    cache_repo: CacheRepository = Depends(get_cache_repo)
):
    """
    Manually clear cache.

    Returns:
        Success status
    """
    try:
        await cache_repo.clear()
        logger.info("Cache cleared by user request")
        return StatusResponse(
            status="success",
            message="Cache cleared"
        )
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")
