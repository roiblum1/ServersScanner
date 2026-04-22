"""
Dependency injection for FastAPI routes.

Provides singleton instances of MongoDB client, server repository,
Kubernetes repository, and dashboard service.
"""

import logging
from ..config import AppConfig, KubernetesConfig
from ..filters import AgentConfig
from ..repositories.kubernetes_repository import KubernetesRepository
from ..repositories.cache_repository import CacheRepository
from ..storage.database.mongo_client import MongoDatabase
from ..storage.database.server_repository import ServerRepository
from ..services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

# Global singletons (set by initialize_dependencies / web_ui startup)
_mongo_db: MongoDatabase = None
_server_repo: ServerRepository = None
_k8s_repo: KubernetesRepository = None
_cache_repo: CacheRepository = None
_dashboard_service: DashboardService = None


def initialize_dependencies() -> None:
    """Initialize all dependency singletons. Called once by create_app()."""
    global _mongo_db, _server_repo, _k8s_repo, _cache_repo, _dashboard_service

    # MongoDB
    _mongo_db = MongoDatabase(AppConfig.MONGO_URI, AppConfig.MONGO_DB_NAME, AppConfig.TLS_VERIFY)
    _server_repo = ServerRepository(_mongo_db)

    # Cache (lightweight in-memory cache for dashboard reads from MongoDB)
    _cache_repo = CacheRepository(ttl_seconds=AppConfig.CACHE_TTL_SECONDS)

    # Kubernetes repository (live queries — only when configured)
    if KubernetesConfig.is_configured():
        agent_config = AgentConfig(
            cluster_names=KubernetesConfig.CLUSTER_NAMES,
            domain_name=KubernetesConfig.DOMAIN_NAME,
            token=KubernetesConfig.TOKEN,
            namespace=KubernetesConfig.NAMESPACE,
        )
        _k8s_repo = KubernetesRepository(agent_config=agent_config)
    else:
        _k8s_repo = None
        logger.info("Kubernetes not configured — K8s live queries disabled")

    # Dashboard service
    _dashboard_service = DashboardService(
        server_repo=_server_repo,
        k8s_repo=_k8s_repo,
        cache_ttl=AppConfig.CACHE_TTL_SECONDS,
    )

    logger.info("Dependencies initialized (storage: MongoDB)")


def get_mongo_db() -> MongoDatabase:
    return _mongo_db


def get_server_repo() -> ServerRepository:
    return _server_repo


def get_cache_repo() -> CacheRepository:
    return _cache_repo


def get_k8s_repo() -> KubernetesRepository:
    return _k8s_repo


def get_dashboard_service() -> DashboardService:
    return _dashboard_service
