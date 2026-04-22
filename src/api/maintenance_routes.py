"""
Maintenance API routes — set, remove, and query per-server maintenance records.

Maintenance data is stored as an embedded sub-document inside each server's
MongoDB document. Changes are immediately visible on the next dashboard load.
"""

from fastapi import APIRouter, Depends, HTTPException
import logging
from ..models.api_responses import (
    MaintenanceInfo,
    StatusResponse,
    ServerDetailsResponse,
)
from ..storage.database.server_repository import ServerRepository
from .dependencies import get_server_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/servers", tags=["maintenance"])


@router.put("/{server_name}/maintenance", response_model=StatusResponse)
async def set_maintenance(
    server_name: str,
    maintenance: MaintenanceInfo,
    server_repo: ServerRepository = Depends(get_server_repo),
):
    """Set server to maintenance mode."""
    try:
        await server_repo.set_maintenance(server_name, maintenance)
        logger.info(f"Maintenance set for {server_name}")
        return StatusResponse(
            status="success",
            server=server_name,
            message=f"Maintenance set for {server_name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting maintenance for {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error setting maintenance: {e}")


@router.delete("/{server_name}/maintenance", response_model=StatusResponse)
async def remove_maintenance(
    server_name: str,
    server_repo: ServerRepository = Depends(get_server_repo),
):
    """Remove maintenance status from server."""
    try:
        await server_repo.remove_maintenance(server_name)
        logger.info(f"Maintenance removed for {server_name}")
        return StatusResponse(
            status="removed",
            server=server_name,
            message=f"Maintenance removed for {server_name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing maintenance for {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error removing maintenance: {e}")


@router.get("/{server_name}", response_model=ServerDetailsResponse)
async def get_server_details(
    server_name: str,
    server_repo: ServerRepository = Depends(get_server_repo),
):
    """Get details for a single server including maintenance status."""
    try:
        doc = await server_repo.get_server(server_name)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")
        return ServerDetailsResponse(name=doc.id, maintenance=doc.maintenance)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting server details for {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting server details: {e}")
