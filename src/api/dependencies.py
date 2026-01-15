"""
Dependency injection for FastAPI routes.

Provides singleton instances of services and repositories.
Supports both file-based and PostgreSQL storage backends.
"""

from pathlib import Path
import logging
from ..repositories import CacheRepository, MaintenanceRepository, KubernetesRepository
from ..storage import MaintenanceStore, MaintenanceStorePostgres
from ..services.dashboard_service import DashboardService
from ..filters import AgentConfig
from ..config import AppConfig, KubernetesConfig, DatabaseConfig

logger = logging.getLogger(__name__)

# Global instances (initialized by create_app)
_cache_repo: CacheRepository = None
_maintenance_repo: MaintenanceRepository = None
_k8s_repo: KubernetesRepository = None
_dashboard_service: DashboardService = None
_maintenance_store = None  # Can be MaintenanceStore or MaintenanceStorePostgres


def initialize_dependencies():
    """Initialize all dependency instances (called by create_app)."""
    global _cache_repo, _maintenance_repo, _k8s_repo, _dashboard_service, _maintenance_store

    # Initialize cache repository
    _cache_repo = CacheRepository(ttl_seconds=AppConfig.CACHE_TTL_SECONDS)

    # Initialize maintenance store based on configuration
    if DatabaseConfig.use_postgres():
        logger.info("Initializing PostgreSQL maintenance storage")
        _maintenance_store = MaintenanceStorePostgres(
            host=DatabaseConfig.POSTGRES_HOST,
            port=DatabaseConfig.POSTGRES_PORT,
            database=DatabaseConfig.POSTGRES_DB,
            user=DatabaseConfig.POSTGRES_USER,
            password=DatabaseConfig.POSTGRES_PASSWORD,
            min_pool_size=DatabaseConfig.POSTGRES_MIN_POOL_SIZE,
            max_pool_size=DatabaseConfig.POSTGRES_MAX_POOL_SIZE
        )
    else:
        logger.info("Initializing file-based maintenance storage")
        _maintenance_store = MaintenanceStore(data_dir=Path(DatabaseConfig.DATA_DIR))

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

    logger.info(f"Dependencies initialized (storage: {DatabaseConfig.STORAGE_BACKEND})")


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
