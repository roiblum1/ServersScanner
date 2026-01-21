"""
Dependency injection for FastAPI routes.

Provides singleton instances of services and repositories.
Supports both in-memory and Redis-based caching.
"""

from pathlib import Path
import logging
from typing import Union
from ..repositories import CacheRepository, MaintenanceRepository, KubernetesRepository
from ..repositories.cache_repository_redis import RedisCacheRepository
from ..storage import MaintenanceStore
from ..services.dashboard_service import DashboardService
from ..filters import AgentConfig
from ..config import AppConfig, KubernetesConfig, RedisConfig

logger = logging.getLogger(__name__)

# Global instances (initialized by create_app)
_cache_repo: Union[CacheRepository, RedisCacheRepository] = None
_maintenance_repo: MaintenanceRepository = None
_k8s_repo: KubernetesRepository = None
_dashboard_service: DashboardService = None
_maintenance_store: MaintenanceStore = None


def initialize_dependencies():
    """Initialize all dependency instances (called by create_app)."""
    global _cache_repo, _maintenance_repo, _k8s_repo, _dashboard_service, _maintenance_store

    # Initialize cache repository (Redis or in-memory)
    if RedisConfig.use_redis():
        logger.info(f"Initializing Redis cache at {RedisConfig.REDIS_HOST}:{RedisConfig.REDIS_PORT}/{RedisConfig.REDIS_DB}")
        _cache_repo = RedisCacheRepository(
            ttl_seconds=AppConfig.CACHE_TTL_SECONDS,
            redis_host=RedisConfig.REDIS_HOST,
            redis_port=RedisConfig.REDIS_PORT,
            redis_db=RedisConfig.REDIS_DB
        )
    else:
        logger.info("Initializing in-memory cache")
        _cache_repo = CacheRepository(ttl_seconds=AppConfig.CACHE_TTL_SECONDS)

    # Initialize file-based maintenance storage
    logger.info("Initializing JSON file-based maintenance storage")
    data_dir = Path(AppConfig.DATA_DIR)
    _maintenance_store = MaintenanceStore(data_dir=data_dir)

    _maintenance_repo = MaintenanceRepository(store=_maintenance_store)

    # Initialize Kubernetes repository
    agent_config = AgentConfig(
        cluster_names=KubernetesConfig.CLUSTER_NAMES,
        domain_name=KubernetesConfig.DOMAIN_NAME,
        token=KubernetesConfig.TOKEN,
        namespace=KubernetesConfig.NAMESPACE
    )
    _k8s_repo = KubernetesRepository(agent_config=agent_config)

    # Initialize dashboard service
    _dashboard_service = DashboardService(
        maintenance_repo=_maintenance_repo,
        k8s_repo=_k8s_repo,
        cache_ttl=AppConfig.CACHE_TTL_SECONDS
    )

    cache_backend = "Redis" if RedisConfig.use_redis() else "in-memory"
    logger.info(f"Dependencies initialized (cache: {cache_backend}, maintenance: JSON file)")


def get_cache_repo() -> CacheRepository:
    """Dependency for cache repository."""
    return _cache_repo


def get_maintenance_repo() -> MaintenanceRepository:
    """Dependency for maintenance repository."""
    return _maintenance_repo


def get_k8s_repo() -> KubernetesRepository:
    """Dependency for Kubernetes repository."""
    return _k8s_repo


def get_dashboard_service() -> DashboardService:
    """Dependency for dashboard service."""
    return _dashboard_service


def get_maintenance_store():
    """Dependency for maintenance store (for initialization)."""
    return _maintenance_store
