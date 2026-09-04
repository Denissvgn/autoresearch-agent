"""Tests for feature specification hashing."""

import pytest

from feature_engineering.spec.hasher import (
    compute_config_hash,
    compute_feature_spec_hash,
    verify_spec_hash,
)


class TestFeatureSpecHashing:
    """Test suite for feature spec hashing."""
    
    def test_compute_feature_spec_hash_deterministic(self):
        """Test that spec hash is deterministic for same inputs."""
        spec = {
            'feature_names': ['feature1', 'feature2', 'feature3'],
            'feature_dtypes': {'feature1': 'float64', 'feature2': 'float64', 'feature3': 'float64'},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        hash1 = compute_feature_spec_hash(spec)
        hash2 = compute_feature_spec_hash(spec)
        
        # Should produce same hash
        assert hash1 == hash2
        
        # Should be 64-character hex string (SHA256)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)
    
    def test_compute_feature_spec_hash_sensitive_to_changes(self):
        """Test that hash changes when spec changes."""
        spec1 = {
            'feature_names': ['feature1', 'feature2'],
            'feature_dtypes': {'feature1': 'float64', 'feature2': 'float64'},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        spec2 = spec1.copy()
        spec2['feature_names'] = ['feature1', 'feature3']  # Changed feature name
        
        hash1 = compute_feature_spec_hash(spec1)
        hash2 = compute_feature_spec_hash(spec2)
        
        # Hashes should differ
        assert hash1 != hash2
    
    def test_compute_feature_spec_hash_order_independent(self):
        """Test that hash is order-dependent for feature names (order matters)."""
        spec1 = {
            'feature_names': ['feature1', 'feature2', 'feature3'],
            'feature_dtypes': {'feature1': 'float64', 'feature2': 'float64', 'feature3': 'float64'},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        # Same features but different order
        spec2 = {
            'feature_names': ['feature3', 'feature1', 'feature2'],
            'feature_dtypes': {'feature3': 'float64', 'feature1': 'float64', 'feature2': 'float64'},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        hash1 = compute_feature_spec_hash(spec1)
        hash2 = compute_feature_spec_hash(spec2)
        
        # Hashes should differ (order matters for feature alignment)
        assert hash1 != hash2
    
    def test_verify_spec_hash_valid(self):
        """Test hash verification with valid hash."""
        spec = {
            'feature_names': ['feature1', 'feature2'],
            'feature_dtypes': {'feature1': 'float64', 'feature2': 'float64'},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        hash_value = compute_feature_spec_hash(spec)
        
        # Verification should pass
        assert verify_spec_hash(spec, hash_value) is True
    
    def test_verify_spec_hash_invalid(self):
        """Test hash verification with invalid hash."""
        spec = {
            'feature_names': ['feature1', 'feature2'],
            'feature_dtypes': {'feature1': 'float64', 'feature2': 'float64'},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        wrong_hash = 'a' * 64  # Invalid hash
        
        # Verification should fail
        assert verify_spec_hash(spec, wrong_hash) is False
    
    def test_compute_config_hash_deterministic(self, sample_feature_config):
        """Test that config hash is deterministic."""
        # Convert to dict for hashing
        config_dict = sample_feature_config.model_dump()
        hash1 = compute_config_hash(config_dict)
        hash2 = compute_config_hash(config_dict)
        
        # Should produce same hash
        assert hash1 == hash2
        
        # Should be 8-character hex string (first 8 chars of SHA256)
        assert len(hash1) == 8
        assert all(c in '0123456789abcdef' for c in hash1)
    
    def test_compute_config_hash_sensitive_to_changes(self, sample_feature_config):
        """Test that config hash changes when config changes."""
        from feature_engineering.core.config import FeatureConfig
        
        config_dict1 = sample_feature_config.model_dump()
        hash1 = compute_config_hash(config_dict1)
        
        # Create modified config
        modified_config = FeatureConfig(
            sma_periods=[7, 14, 28],  # Changed from original
            ema_periods=sample_feature_config.ema_periods,
            rsi_periods=sample_feature_config.rsi_periods,
            macd_fast=sample_feature_config.macd_fast,
            macd_slow=sample_feature_config.macd_slow,
            macd_signal=sample_feature_config.macd_signal,
            bb_period=sample_feature_config.bb_period,
            bb_std=sample_feature_config.bb_std,
            atr_period=sample_feature_config.atr_period,
            volume_sma_periods=sample_feature_config.volume_sma_periods,
            price_change_periods=sample_feature_config.price_change_periods,
            volatility_periods=sample_feature_config.volatility_periods,
        )
        
        config_dict2 = modified_config.model_dump()
        hash2 = compute_config_hash(config_dict2)
        
        # Hashes should differ
        assert hash1 != hash2


class TestHashingEdgeCases:
    """Test edge cases in hashing."""
    
    def test_empty_feature_names(self):
        """Test hashing with empty feature names."""
        spec = {
            'feature_names': [],
            'feature_dtypes': {},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        hash_value = compute_feature_spec_hash(spec)
        
        # Should still produce valid hash
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64
    
    def test_unicode_feature_names(self):
        """Test hashing with unicode feature names."""
        spec = {
            'feature_names': ['特征1', 'feature_2', 'функция_3'],
            'feature_dtypes': {'特征1': 'float64', 'feature_2': 'float64', 'функция_3': 'float64'},
            'library_version': '1.0.0',
            'feature_spec_version': '1.0',
        }
        
        hash_value = compute_feature_spec_hash(spec)
        
        # Should handle unicode without errors
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64
