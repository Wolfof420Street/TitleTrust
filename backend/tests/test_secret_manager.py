"""
Tests for the SecretManager module.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from backend.security.secret_manager import (
    SecretManager,
    EnvironmentSecretProvider,
    GCPSecretManagerProvider,
    get_secret_manager,
    init_secret_manager,
)


class TestEnvironmentSecretProvider:
    """Test environment variable secret provider."""

    def test_get_secret_from_environment(self):
        """Verify secrets are retrieved from environment."""
        with patch.dict(os.environ, {"TEST_SECRET": "secret_value"}):
            provider = EnvironmentSecretProvider()
            assert provider.get_secret("test-secret") == "secret_value"

    def test_get_missing_secret_returns_none(self):
        """Verify missing secrets return None."""
        provider = EnvironmentSecretProvider()
        result = provider.get_secret("non-existent-secret")
        assert result is None

    def test_get_json_secret(self):
        """Verify JSON secrets are parsed."""
        with patch.dict(os.environ, {"API_KEYS": '{"key1": "value1", "key2": "value2"}'}):
            provider = EnvironmentSecretProvider()
            result = provider.get_secret_json("api-keys")
            assert result == {"key1": "value1", "key2": "value2"}

    def test_get_invalid_json_returns_none(self):
        """Verify invalid JSON returns None."""
        with patch.dict(os.environ, {"INVALID_JSON": "not valid json"}):
            provider = EnvironmentSecretProvider()
            result = provider.get_secret_json("invalid-json")
            assert result is None


class TestGCPSecretManagerProvider:
    """Test GCP Secret Manager provider."""

    def test_fallback_to_environment_without_gcp(self):
        """Verify fallback to environment when GCP unavailable."""
        with patch.dict(os.environ, {"TEST_SECRET": "env_value"}):
            provider = GCPSecretManagerProvider("test-project")
            # Should fall back to environment since no client
            assert provider.get_secret("test-secret") == "env_value"

    def test_cache_ttl_configuration(self):
        """Verify cache TTL is configurable."""
        provider = GCPSecretManagerProvider("test-project", cache_ttl_minutes=120)
        assert provider.cache_ttl == timedelta(minutes=120)

    def test_cache_invalidation(self):
        """Verify cache expires after TTL."""
        provider = GCPSecretManagerProvider("test-project", cache_ttl_minutes=1)
        
        # Store in cache with expired timestamp
        provider._cache["test"] = ("value", datetime.now() - timedelta(minutes=2))
        assert not provider._is_cache_valid("test")

    def test_clear_cache(self):
        """Verify cache can be cleared."""
        provider = GCPSecretManagerProvider("test-project")
        provider._cache["test"] = ("value", datetime.now() + timedelta(hours=1))
        
        provider.clear_cache()
        assert len(provider._cache) == 0

    def test_get_cache_stats(self):
        """Verify cache statistics."""
        provider = GCPSecretManagerProvider("test-project")
        provider._cache["test"] = ("value", datetime.now() + timedelta(hours=1))
        
        stats = provider.get_cache_stats()
        assert stats["cached_secrets"] == 1
        assert stats["valid_secrets"] == 1


class TestSecretManager:
    """Test unified SecretManager."""

    def test_initialization_with_environment_fallback(self):
        """Verify initialization with environment fallback."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}, clear=True):
            manager = SecretManager(use_gcp=False)
            assert isinstance(manager.provider, EnvironmentSecretProvider)

    def test_get_secret_required(self):
        """Verify required secret raises error when missing."""
        manager = SecretManager(use_gcp=False)
        with pytest.raises(ValueError):
            manager.get_secret("missing-secret", required=True)

    def test_get_secret_optional(self):
        """Verify optional secret returns None when missing."""
        manager = SecretManager(use_gcp=False)
        result = manager.get_secret("missing-secret", required=False)
        assert result is None

    def test_get_secret_from_environment(self):
        """Verify secrets retrieved from environment."""
        with patch.dict(os.environ, {"JWT_SECRET": "test_jwt_secret"}):
            manager = SecretManager(use_gcp=False)
            result = manager.get_jwt_secret()
            assert result == "test_jwt_secret"

    def test_get_database_url(self):
        """Verify database URL retrieval."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/db"}):
            manager = SecretManager(use_gcp=False)
            url = manager.get_database_url()
            assert url == "postgresql://localhost/db"

    def test_get_firebase_config(self):
        """Verify Firebase config retrieval."""
        config_json = '{"apiKey": "key123", "projectId": "project123"}'
        with patch.dict(os.environ, {"FIREBASE_CONFIG": config_json}):
            manager = SecretManager(use_gcp=False)
            config = manager.get_firebase_config()
            assert config["apiKey"] == "key123"

    def test_get_api_keys(self):
        """Verify API keys retrieval."""
        keys_json = '{"google": "key1", "stripe": "key2"}'
        with patch.dict(os.environ, {"API_KEYS": keys_json}):
            manager = SecretManager(use_gcp=False)
            keys = manager.get_api_keys()
            assert keys["google"] == "key1"
            assert keys["stripe"] == "key2"

    def test_get_stats(self):
        """Verify manager statistics."""
        manager = SecretManager(use_gcp=False)
        stats = manager.get_stats()
        assert stats["provider"] == "EnvironmentSecretProvider"
        assert stats["cache_ttl_minutes"] == 60

    def test_clear_cache(self):
        """Verify cache clearing."""
        manager = SecretManager(use_gcp=False)
        # Should not raise error
        manager.clear_cache()


class TestGlobalSecretManager:
    """Test global SecretManager instance."""

    def test_get_global_instance(self):
        """Verify global instance creation."""
        manager1 = get_secret_manager()
        manager2 = get_secret_manager()
        assert manager1 is manager2

    def test_init_global_instance(self):
        """Verify global instance initialization."""
        manager = init_secret_manager(use_gcp=False)
        assert isinstance(manager.provider, EnvironmentSecretProvider)

    def test_global_instance_reuse(self):
        """Verify global instance reuse."""
        manager1 = init_secret_manager(use_gcp=False)
        manager2 = get_secret_manager()
        assert manager1 is manager2


# Test markers
pytestmark = [
    pytest.mark.security,
    pytest.mark.unit,
]
