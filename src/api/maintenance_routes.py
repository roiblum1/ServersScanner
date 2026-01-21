"""
Maintenance API routes for server maintenance management.

Provides endpoints for setting, removing, and querying server
maintenance status.
"""

from fastapi import APIRouter, Depends, HTTPException
import logging
from ..models.api_responses import (
    MaintenanceInfo,
    StatusResponse,
    ServerDetailsResponse
)
from ..repositories import MaintenanceRepository
from .dependencies import get_maintenance_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/servers", tags=["maintenance"])


@router.put("/{server_name}/maintenance", response_model=StatusResponse)
async def set_maintenance(
    server_name: str,
    maintenance: MaintenanceInfo,
    maintenance_repo: MaintenanceRepository = Depends(get_maintenance_repo)
):
    """
    Set server to maintenance mode.

    Args:
        server_name: Server profile name
        maintenance: Maintenance information (reason, severity, timestamp)

    Returns:
        Success status

    Note:
        Changes are immediately visible on next API call due to hybrid caching.
    """
    try:
        # Store maintenance record
        await maintenance_repo.set(server_name, maintenance)

        logger.info(f"Maintenance set for {server_name}, will be visible on next API call")

        return StatusResponse(
            status="success",
            server=server_name,
            message=f"Maintenance set for {server_name}"
        )

    except Exception as e:
        logger.error(f"Error setting maintenance for {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error setting maintenance: {str(e)}")


@router.delete("/{server_name}/maintenance", response_model=StatusResponse)
async def remove_maintenance(
    server_name: str,
    maintenance_repo: MaintenanceRepository = Depends(get_maintenance_repo)
):
    """
    Remove maintenance status from server.

    Args:
        server_name: Server profile name

    Returns:
        Success status

    Note:
        Changes are immediately visible on next API call due to hybrid caching.
    """
    try:
        await maintenance_repo.remove(server_name)

        logger.info(f"Maintenance removed for {server_name}, will be visible on next API call")

        return StatusResponse(
            status="removed",
            server=server_name,
            message=f"Maintenance removed for {server_name}"
        )

    except Exception as e:
        logger.error(f"Error removing maintenance for {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error removing maintenance: {str(e)}")


@router.get("/{server_name}", response_model=ServerDetailsResponse)
async def get_server_details(
    server_name: str,
    maintenance_repo: MaintenanceRepository = Depends(get_maintenance_repo)
):
    """
    Get details for a single server including maintenance status.

    Args:
        server_name: Server profile name

    Returns:
        Server details with maintenance info if applicable
    """
    try:
        # Get maintenance info
        maintenance = await maintenance_repo.get(server_name)

        return ServerDetailsResponse(
            name=server_name,
            maintenance=maintenance
        )

    except Exception as e:
        logger.error(f"Error getting server details for {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting server details: {str(e)}")
