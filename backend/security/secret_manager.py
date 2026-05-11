"""
GCP Secret Manager abstraction with fallback to environment variables.

Handles secure retrieval and caching of secrets with automatic rotation support.
"""

import os
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class SecretProvider(ABC):
    """Abstract base for secret providers."""

    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve secret by name."""
        pass

    @abstractmethod
    def get_secret_json(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve secret and parse as JSON."""
        pass


class EnvironmentSecretProvider(SecretProvider):
    """Fallback provider that reads from environment variables."""

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Get secret from environment variable."""
        env_var = secret_name.upper().replace("-", "_")
        value = os.getenv(env_var)
        if not value:
            logger.warning(f"Secret not found in environment: {env_var}")
        return value

    def get_secret_json(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """Get JSON secret from environment variable."""
        value = self.get_secret(secret_name)
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON secret: {secret_name}")
            return None


class GCPSecretManagerProvider(SecretProvider):
    """GCP Secret Manager provider for retrieving secrets."""

    def __init__(self, project_id: str, cache_ttl_minutes: int = 60):
        """
        Initialize GCP Secret Manager provider.
        
        Args:
            project_id: GCP project ID
            cache_ttl_minutes: Cache TTL in minutes (default 60)
        """
        self.project_id = project_id
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._cache: Dict[str, tuple] = {}  # (value, expires_at)
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize GCP Secret Manager client."""
        try:
            from google.cloud import secretmanager
            self._client = secretmanager.SecretManagerServiceClient()
        except ImportError:
            logger.warning("google-cloud-secret-manager not installed. Using environment fallback.")
            self._client = None
        except Exception as e:
            logger.warning(f"Failed to initialize GCP Secret Manager: {e}. Using environment fallback.")
            self._client = None

    def _is_cache_valid(self, secret_name: str) -> bool:
        """Check if cached secret is still valid."""
        if secret_name not in self._cache:
            return False
        _, expires_at = self._cache[secret_name]
        return datetime.now() < expires_at

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve secret from GCP Secret Manager or cache."""
        # Check cache first
        if self._is_cache_valid(secret_name):
            value, _ = self._cache[secret_name]
            logger.debug(f"Secret from cache: {secret_name}")
            return value

        # Fall back if no client
        if not self._client:
            logger.debug(f"Using environment provider for: {secret_name}")
            return EnvironmentSecretProvider().get_secret(secret_name)

        try:
            # Build secret name
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            
            # Access the secret version
            response = self._client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            
            # Cache the secret
            self._cache[secret_name] = (secret_value, datetime.now() + self.cache_ttl)
            logger.debug(f"Secret retrieved from GCP: {secret_name}")
            
            return secret_value
        except Exception as e:
            logger.error(f"Failed to retrieve secret from GCP: {secret_name} - {e}")
            # Fall back to environment
            return EnvironmentSecretProvider().get_secret(secret_name)

    def get_secret_json(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve JSON secret from GCP Secret Manager."""
        value = self.get_secret(secret_name)
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON secret: {secret_name}")
            return None

    def clear_cache(self):
        """Clear secret cache."""
        self._cache.clear()
        logger.info("Secret cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cached_secrets": len(self._cache),
            "valid_secrets": sum(1 for _, (_, expires) in self._cache.items() if datetime.now() < expires)
        }


class SecretManager:
    """
    Unified secret manager with support for multiple providers.
    
    Implements a strategy pattern for flexible secret retrieval with
    automatic fallback and caching.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        cache_ttl_minutes: int = 60,
        use_gcp: bool = True
    ):
        """
        Initialize SecretManager.
        
        Args:
            project_id: GCP project ID (uses GOOGLE_CLOUD_PROJECT env var if not provided)
            cache_ttl_minutes: Cache TTL in minutes
            use_gcp: Whether to try GCP Secret Manager (true) or only use environment (false)
        """
        self.cache_ttl_minutes = cache_ttl_minutes
        
        # Determine primary provider
        if use_gcp:
            project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
            if project_id:
                self.provider = GCPSecretManagerProvider(project_id, cache_ttl_minutes)
                logger.info(f"Using GCP Secret Manager for project: {project_id}")
            else:
                self.provider = EnvironmentSecretProvider()
                logger.info("Using environment variable fallback (no GCP project configured)")
        else:
            self.provider = EnvironmentSecretProvider()
            logger.info("Using environment variable provider")

    def get_secret(self, secret_name: str, required: bool = True) -> Optional[str]:
        """
        Retrieve a secret by name.
        
        Args:
            secret_name: Name of the secret
            required: If True, raise error if secret not found
            
        Returns:
            Secret value or None if not found
            
        Raises:
            ValueError: If required=True and secret not found
        """
        value = self.provider.get_secret(secret_name)
        if required and not value:
            raise ValueError(f"Required secret not found: {secret_name}")
        return value

    def get_secret_json(self, secret_name: str, required: bool = True) -> Optional[Dict[str, Any]]:
        """
        Retrieve a JSON secret by name.
        
        Args:
            secret_name: Name of the secret
            required: If True, raise error if secret not found
            
        Returns:
            Parsed JSON secret or None if not found
            
        Raises:
            ValueError: If required=True and secret not found
        """
        value = self.provider.get_secret_json(secret_name)
        if required and not value:
            raise ValueError(f"Required JSON secret not found: {secret_name}")
        return value

    def get_database_url(self, required: bool = True) -> Optional[str]:
        """Get database connection URL."""
        return self.get_secret("database-url", required=required)

    def get_firebase_config(self, required: bool = False) -> Optional[Dict[str, Any]]:
        """Get Firebase configuration."""
        return self.get_secret_json("firebase-config", required=required)

    def get_jwt_secret(self, required: bool = True) -> Optional[str]:
        """Get JWT signing secret."""
        return self.get_secret("jwt-secret", required=required)

    def get_api_keys(self, required: bool = False) -> Optional[Dict[str, str]]:
        """Get API keys dictionary."""
        return self.get_secret_json("api-keys", required=required)

    def clear_cache(self):
        """Clear secret cache if supported by provider."""
        if hasattr(self.provider, "clear_cache"):
            self.provider.clear_cache()

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        return {
            "provider": self.provider.__class__.__name__,
            "cache_ttl_minutes": self.cache_ttl_minutes,
            **({} if not hasattr(self.provider, "get_cache_stats") else self.provider.get_cache_stats())
        }


# Global instance
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """Get global SecretManager instance."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def init_secret_manager(
    project_id: Optional[str] = None,
    cache_ttl_minutes: int = 60,
    use_gcp: bool = True
) -> SecretManager:
    """Initialize global SecretManager instance."""
    global _secret_manager
    _secret_manager = SecretManager(project_id, cache_ttl_minutes, use_gcp)
    return _secret_manager
