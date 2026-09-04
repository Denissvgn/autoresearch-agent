"""Tests for feature specification generation."""

import pytest

from feature_engineering.spec.generator import (
    extract_feature_dtypes,
    generate_feature_spec,
    summarize_lookbacks,
)


class TestFeatureSpecGeneration:
    """Test suite for feature specification generation."""
    
    def test_generate_feature_spec(self, sample_ohlcv_data, sample_feature_config):
        """Test feature spec generation returns all required fields."""
        from feature_engineering.core.indicators import FeatureEngineer
        
        engineer = FeatureEngineer(sample_feature_config)
        features_df = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Function takes feature_names list, not DataFrame
        feature_names = list(features_df.columns)
        feature_dtypes = extract_feature_dtypes(features_df)
        spec = generate_feature_spec(feature_names, feature_dtypes, sample_feature_config)
        
        # Check required fields exist
        assert 'feature_spec_id' in spec
        assert 'library_version' in spec
        assert 'feature_spec_version' in spec
        assert 'feature_count' in spec
        assert 'feature_names' in spec
        assert 'feature_dtypes' in spec
        assert 'config' in spec
        assert 'indicator_lookbacks' in spec
        assert 'created_at' in spec
        
        # Check types
        assert isinstance(spec['feature_spec_id'], str)
        assert isinstance(spec['library_version'], str)
        assert isinstance(spec['feature_spec_version'], str)
        assert isinstance(spec['feature_count'], int)
        assert isinstance(spec['feature_names'], list)
        assert isinstance(spec['feature_dtypes'], dict)
        assert isinstance(spec['config'], dict)
        assert isinstance(spec['indicator_lookbacks'], dict)
        assert isinstance(spec['created_at'], str)
    
    def test_feature_spec_id_deterministic(self, sample_ohlcv_data, sample_feature_config):
        """Test that feature spec ID includes timestamp and config hash."""
        from feature_engineering.core.indicators import FeatureEngineer
        from datetime import datetime, timezone
        
        engineer = FeatureEngineer(sample_feature_config)
        features_df = engineer.calculate_all_features(sample_ohlcv_data)
        feature_names = list(features_df.columns)
        feature_dtypes = extract_feature_dtypes(features_df)
        
        # Generate specs with same timestamp to test determinism
        timestamp = datetime.now(timezone.utc)
        spec1 = generate_feature_spec(feature_names, feature_dtypes, sample_feature_config, created_at=timestamp)
        spec2 = generate_feature_spec(feature_names, feature_dtypes, sample_feature_config, created_at=timestamp)
        
        # Same timestamp and config should give same spec_id
        assert spec1['feature_spec_id'] == spec2['feature_spec_id']
        assert spec1['created_at'] == spec2['created_at']
    
    def test_feature_spec_id_format(self, sample_ohlcv_data, sample_feature_config):
        """Test feature spec ID format."""
        from feature_engineering.core.indicators import FeatureEngineer
        
        engineer = FeatureEngineer(sample_feature_config)
        features_df = engineer.calculate_all_features(sample_ohlcv_data)
        feature_names = list(features_df.columns)
        feature_dtypes = extract_feature_dtypes(features_df)
        
        spec = generate_feature_spec(feature_names, feature_dtypes, sample_feature_config)
        spec_id = spec['feature_spec_id']
        
        # Format: f_v{version}_{timestamp}_{config_hash}
        assert spec_id.startswith('f_v')
        parts = spec_id.split('_')
        assert len(parts) >= 4  # f, v{version}, {timestamp}, {hash}
    
    def test_extract_feature_dtypes(self, sample_ohlcv_data, sample_feature_config):
        """Test feature dtype extraction."""
        from feature_engineering.core.indicators import FeatureEngineer
        
        engineer = FeatureEngineer(sample_feature_config)
        features_df = engineer.calculate_all_features(sample_ohlcv_data)
        
        dtypes = extract_feature_dtypes(features_df)
        
        # Should be dict mapping feature names to dtype strings
        assert isinstance(dtypes, dict)
        assert len(dtypes) == len(features_df.columns)
        
        # All values should be strings
        for dtype in dtypes.values():
            assert isinstance(dtype, str)
    
    def test_summarize_lookbacks(self, sample_feature_config):
        """Test lookback summary calculation."""
        from feature_engineering.core.indicators import compute_indicator_lookbacks
        
        lookbacks = compute_indicator_lookbacks(sample_feature_config)
        summary = summarize_lookbacks(lookbacks)
        
        # Check required fields
        assert 'max_lookback' in summary
        assert 'total_indicators' in summary
        assert 'indicators' in summary
        
        # Check types
        assert isinstance(summary['max_lookback'], int)
        assert isinstance(summary['total_indicators'], int)
        assert isinstance(summary['indicators'], list)
        
        # Max lookback should be positive
        assert summary['max_lookback'] > 0
        assert summary['total_indicators'] > 0
    
    def test_config_serialization(self, sample_feature_config):
        """Test that config is properly serialized in spec."""
        feature_names = ['feature1']
        feature_dtypes = {'feature1': 'int64'}
        spec = generate_feature_spec(feature_names, feature_dtypes, sample_feature_config)
        
        config_dict = spec['config']
        
        # Check that config fields are present
        assert 'sma_periods' in config_dict
        assert 'ema_periods' in config_dict
        assert 'rsi_periods' in config_dict
        
        # Check that values match original config
        assert config_dict['sma_periods'] == sample_feature_config.sma_periods
        assert config_dict['ema_periods'] == sample_feature_config.ema_periods


class TestFeatureSpecEdgeCases:
    """Test edge cases in spec generation."""
    
    def test_empty_dataframe(self, sample_feature_config):
        """Test spec generation with empty features list."""
        feature_names = []
        feature_dtypes = {}
        spec = generate_feature_spec(feature_names, feature_dtypes, sample_feature_config)
        
        # Should still generate valid spec
        assert spec['feature_count'] == 0
        assert spec['feature_names'] == []
        assert spec['feature_dtypes'] == {}
    
    def test_single_feature(self, sample_feature_config):
        """Test spec generation with single feature."""
        feature_names = ['feature1']
        feature_dtypes = {'feature1': 'float64'}
        spec = generate_feature_spec(feature_names, feature_dtypes, sample_feature_config)
        
        assert spec['feature_count'] == 1
        assert spec['feature_names'] == ['feature1']
        assert 'feature1' in spec['feature_dtypes']
