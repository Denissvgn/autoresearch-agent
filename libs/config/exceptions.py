"""
Configuration exceptions for the TRAID Platform config library.

This module defines custom exceptions for configuration-related errors.
"""


class ConfigurationError(Exception):
    """Base exception for configuration errors."""
    pass


class VaultConfigurationError(ConfigurationError):
    """Exception raised when Vault configuration fails."""
    pass


class ValidationError(ConfigurationError):
    """Exception raised when configuration validation fails."""
    pass


class EnvironmentError(ConfigurationError):
    """Exception raised when environment configuration is invalid."""
    pass


class SecretMaskingError(ConfigurationError):
    """Exception raised when secret masking fails."""
    pass