"""
Kubernetes cluster configuration.
"""

import os


class KubernetesConfig:
    """Kubernetes cluster connection settings and token management."""

    CLUSTER_NAMES = os.getenv("K8S_CLUSTER_NAMES", "")
    DOMAIN_NAME = os.getenv("K8S_DOMAIN_NAME", "")
    TOKEN = os.getenv("K8S_TOKEN", "")
    NAMESPACE = os.getenv("K8S_NAMESPACE", "assisted-installer")

    @classmethod
    def is_configured(cls) -> bool:
        """Return True if all required K8s settings are present."""
        return all([cls.CLUSTER_NAMES, cls.DOMAIN_NAME, cls.TOKEN])

    @classmethod
    def get_cluster_list(cls) -> list:
        """Return parsed list of cluster names."""
        return [c.strip() for c in cls.CLUSTER_NAMES.split(",") if c.strip()]

    @classmethod
    def get_token_list(cls) -> list:
        """Return parsed list of per-cluster tokens."""
        return [t.strip() for t in cls.TOKEN.split(",") if t.strip()]
