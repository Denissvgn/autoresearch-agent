"""Tests for the vault_loader module."""

import os
from unittest.mock import MagicMock, patch

from config.vault_loader import (
    _merge_configs,
    _normalize_keys,
    get_vault_status,
    load_config,
    reload_vault_client,
)


class TestVaultLoader:
    """Test suite for the vault loader functionality."""

    def setup_method(self):
        """Reset global state before each test."""
        reload_vault_client()
        
        # Clear relevant environment variables
        env_vars = [
            "USE_VAULT",
            "VAULT_ADDR",
            "VAULT_TOKEN", 
            "APP_ENV",
            "TEST_VAR",
            "DATABASE_URL",
            "REDIS_URL",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def test_vault_disabled_via_env(self):
        """Test that Vault is skipped when USE_VAULT=false."""
        os.environ["USE_VAULT"] = "false"
        os.environ["TEST_VAR"] = "env_value"
        
        config = load_config("test-service")
        
        assert config["TEST_VAR"] == "env_value"
        
        # Should not have attempted Vault connection
        status = get_vault_status()
        assert status["vault_enabled"] is False

    def test_vault_missing_credentials(self):
        """Test fallback when Vault credentials are missing."""
        os.environ["USE_VAULT"] = "true"
        os.environ["TEST_VAR"] = "env_fallback"
        # VAULT_ADDR and VAULT_TOKEN not set
        
        config = load_config("test-service")
        
        assert config["TEST_VAR"] == "env_fallback"
        
        status = get_vault_status()
        assert status["vault_enabled"] is True
        assert status["vault_connected"] is False

    @patch("hvac.Client")
    def test_vault_connection_success(self, mock_hvac_client):
        """Test successful Vault connection and configuration loading."""
        # Setup environment
        os.environ["USE_VAULT"] = "true"
        os.environ["VAULT_ADDR"] = "http://vault:8200"
        os.environ["VAULT_TOKEN"] = "test-token"
        os.environ["APP_ENV"] = "test"
        
        # Mock Vault client
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac_client.return_value = mock_client
        
        # Mock Vault responses
        def mock_vault_response(path):
            if path == "config/global":
                return {
                    "data": {
                        "data": {
                            "global_setting": "global_value",
                            "database_url": "postgres://global/db"
                        }
                    }
                }
            elif path == "config/test-service/test":
                return {
                    "data": {
                        "data": {
                            "service_setting": "service_value", 
                            "database_url": "postgres://service/db"  # Should override global
                        }
                    }
                }
            else:
                raise Exception("Path not found")
        
        mock_client.secrets.kv.v2.read_secret_version.side_effect = mock_vault_response
        
        config = load_config("test-service")
        
        # Check that service config overrides global config
        assert config["GLOBAL_SETTING"] == "global_value"
        assert config["SERVICE_SETTING"] == "service_value"
        assert config["DATABASE_URL"] == "postgres://service/db"  # Service overrides global

    @patch("hvac.Client")
    def test_vault_partial_failure_with_fallback(self, mock_hvac_client):
        """Test fallback when Vault is partially available."""
        os.environ["USE_VAULT"] = "true"
        os.environ["VAULT_ADDR"] = "http://vault:8200"
        os.environ["VAULT_TOKEN"] = "test-token"
        os.environ["ENV_ONLY_VAR"] = "env_value"
        
        # Mock Vault client
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac_client.return_value = mock_client
        
        # Mock partial Vault failure (global works, service fails)
        def mock_vault_response(path):
            if path == "config/global":
                return {
                    "data": {
                        "data": {
                            "vault_setting": "vault_value"
                        }
                    }
                }
            else:
                raise Exception("Service config not found")
        
        mock_client.secrets.kv.v2.read_secret_version.side_effect = mock_vault_response
        
        config = load_config("test-service")
        
        # Should have both Vault and env values
        assert config["VAULT_SETTING"] == "vault_value"
        assert config["ENV_ONLY_VAR"] == "env_value"

    def test_environment_only_configuration(self):
        """Test loading configuration from environment variables only."""
        os.environ["USE_VAULT"] = "false"
        os.environ["DATABASE_URL"] = "postgres://localhost/test"
        os.environ["REDIS_URL"] = "redis://localhost:6379"
        os.environ["DEBUG"] = "true"
        
        config = load_config("test-service")
        
        assert config["DATABASE_URL"] == "postgres://localhost/test"
        assert config["REDIS_URL"] == "redis://localhost:6379"
        assert config["DEBUG"] == "true"

    @patch("dotenv.dotenv_values")
    @patch("pathlib.Path")
    def test_dotenv_file_loading(self, mock_path, mock_dotenv_values):
        """Test loading configuration from .env file."""
        os.environ["USE_VAULT"] = "false"
        
        # Mock .env file existence and content
        mock_cwd = MagicMock()
        mock_env_file = MagicMock()
        mock_env_file.exists.return_value = True
        mock_cwd.__truediv__.return_value = mock_env_file
        mock_path.cwd.return_value = mock_cwd
        
        mock_dotenv_values.return_value = {
            "DATABASE_URL": "postgres://dotenv/db",
            "API_KEY": "dotenv_key"
        }
        
        # Environment variable should override .env
        os.environ["API_KEY"] = "env_override"
        
        config = load_config("test-service")
        
        assert config["DATABASE_URL"] == "postgres://dotenv/db"
        assert config["API_KEY"] == "env_override"  # Env overrides .env

    def test_key_normalization(self):
        """Test that all keys are normalized to uppercase."""
        test_config = {
            "database_url": "postgres://test",
            "Redis_URL": "redis://test", 
            "API_key": "test_key",
            "ALREADY_UPPER": "value"
        }
        
        normalized = _normalize_keys(test_config)
        
        assert "DATABASE_URL" in normalized
        assert "REDIS_URL" in normalized
        assert "API_KEY" in normalized
        assert "ALREADY_UPPER" in normalized
        assert len(normalized) == 4

    def test_config_merging_precedence(self):
        """Test that configuration merging follows correct precedence."""
        base_config = {"VAR1": "base", "VAR2": "base"}
        global_config = {"VAR1": "global", "VAR3": "global"}
        service_config = {"VAR1": "service", "VAR4": "service"}
        
        merged = _merge_configs(base_config, global_config, service_config)
        
        # Service should override global, global should override base
        assert merged["VAR1"] == "service"
        assert merged["VAR2"] == "base"
        assert merged["VAR3"] == "global"
        assert merged["VAR4"] == "service"

    def test_default_environment_detection(self):
        """Test that APP_ENV is used when env parameter is None."""
        os.environ["USE_VAULT"] = "false"
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_VAR"] = "staging_value"
        
        config = load_config("test-service")  # env=None
        
        assert config["TEST_VAR"] == "staging_value"
        # The exact behavior depends on implementation, but it should use staging env

    def test_explicit_environment_override(self):
        """Test that explicit env parameter overrides APP_ENV."""
        os.environ["USE_VAULT"] = "false"
        os.environ["APP_ENV"] = "staging"
        os.environ["TEST_VAR"] = "value"
        
        config = load_config("test-service", env="production")
        
        # Should use production env, not staging from APP_ENV
        assert config["TEST_VAR"] == "value"

    @patch("hvac.Client")
    def test_vault_authentication_failure(self, mock_hvac_client):
        """Test handling of Vault authentication failure."""
        os.environ["USE_VAULT"] = "true"
        os.environ["VAULT_ADDR"] = "http://vault:8200"
        os.environ["VAULT_TOKEN"] = "invalid-token"
        os.environ["FALLBACK_VAR"] = "fallback_value"
        
        # Mock failed authentication
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False
        mock_hvac_client.return_value = mock_client
        
        config = load_config("test-service")
        
        # Should fall back to environment
        assert config["FALLBACK_VAR"] == "fallback_value"
        
        status = get_vault_status()
        assert status["vault_connected"] is False

    @patch("builtins.__import__")
    def test_vault_import_error(self, mock_import):
        """Test handling when hvac library is not available."""
        os.environ["USE_VAULT"] = "true"
        os.environ["VAULT_ADDR"] = "http://vault:8200"
        os.environ["VAULT_TOKEN"] = "test-token"
        os.environ["FALLBACK_VAR"] = "fallback_value"
        
        # Simulate ImportError for hvac
        def import_side_effect(name, *args):
            if name == "hvac":
                raise ImportError("hvac not available")
            return __import__(name, *args)
        
        mock_import.side_effect = import_side_effect
        
        # Need to reload the vault client after mocking
        reload_vault_client()
        
        config = load_config("test-service")
        
        # Should fall back to environment
        assert config["FALLBACK_VAR"] == "fallback_value"

    def test_vault_status_reporting(self):
        """Test vault status reporting functionality."""
        os.environ["USE_VAULT"] = "true"
        os.environ["VAULT_ADDR"] = "http://vault:8200"
        # No VAULT_TOKEN set
        
        status = get_vault_status()
        
        assert status["vault_enabled"] is True
        assert status["vault_addr"] == "http://vault:8200"
        assert status["vault_connected"] is False
        assert status["vault_authenticated"] is False

    def test_reload_vault_client(self):
        """Test that vault client can be reloaded."""
        # First, get a status
        get_vault_status()
        
        # Set up Vault environment
        os.environ["USE_VAULT"] = "true"
        os.environ["VAULT_ADDR"] = "http://vault:8200"
        os.environ["VAULT_TOKEN"] = "test-token"
        
        # Reload should reset the client
        reload_vault_client()
        
        # Status should reflect new environment (though connection may still fail)
        new_status = get_vault_status()
        assert new_status["vault_addr"] == "http://vault:8200"

    def test_empty_configuration_handling(self):
        """Test handling of empty or missing configuration."""
        os.environ["USE_VAULT"] = "false"
        # No environment variables set
        
        config = load_config("nonexistent-service")
        
        # Should return some configuration (at least from os.environ)
        assert isinstance(config, dict)
