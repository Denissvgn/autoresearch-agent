"""Tests for feature consistency validation."""

import numpy as np
import pandas as pd
import pytest

from feature_engineering.validation import (
    compare_feature_statistics,
    validate_feature_consistency,
)


class TestFeatureConsistencyValidation:
    """Test suite for feature consistency validation."""
    
    def test_validate_identical_features(self, sample_ohlcv_data):
        """Test validation with identical feature sets."""
        df1 = sample_ohlcv_data.copy()
        df2 = sample_ohlcv_data.copy()
        
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        # Should be consistent
        assert is_consistent is True
        assert diff_report['consistent'] == True
        assert diff_report['total_columns'] == len(df1.columns)
    
    def test_validate_slightly_different_features(self, sample_ohlcv_data):
        """Test validation with small numerical differences."""
        df1 = sample_ohlcv_data.copy()
        df2 = sample_ohlcv_data.copy()
        
        # Add small noise to second DataFrame
        df2['close'] = df2['close'] + np.random.randn(len(df2)) * 1e-8
        
        # Should still be consistent with tolerance
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        assert is_consistent is True
    
    def test_validate_significantly_different_features(self, sample_ohlcv_data):
        """Test validation with significant differences."""
        df1 = sample_ohlcv_data.copy()
        df2 = sample_ohlcv_data.copy()
        
        # Add large noise to second DataFrame
        df2['close'] = df2['close'] + np.random.randn(len(df2)) * 10.0
        
        # Should detect mismatch
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        assert is_consistent is False
        assert diff_report['error'] == 'value_mismatches'
        # Check that 'close' is in the mismatches
        mismatch_cols = [m['column'] for m in diff_report['mismatches']]
        assert 'close' in mismatch_cols
    
    def test_validate_missing_features(self, sample_ohlcv_data):
        """Test validation with missing features."""
        df1 = sample_ohlcv_data.copy()
        df2 = sample_ohlcv_data[['open', 'high', 'low']].copy()  # Missing 'close' and 'volume'
        
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        # Should detect mismatch due to missing columns
        assert is_consistent is False
        assert len(diff_report['missing_in_library']) > 0 or len(diff_report['missing_in_legacy']) > 0
    
    def test_validate_with_nan_values(self):
        """Test validation with NaN values."""
        df1 = pd.DataFrame({
            'feature1': [1.0, 2.0, np.nan, 4.0],
            'feature2': [5.0, 6.0, 7.0, 8.0],
        })
        
        df2 = pd.DataFrame({
            'feature1': [1.0, 2.0, np.nan, 4.0],
            'feature2': [5.0, 6.0, 7.0, 8.0],
        })
        
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        # Should handle NaN values properly
        assert is_consistent is True
    
    def test_compare_feature_statistics(self):
        """Test feature statistics comparison."""
        df1 = pd.DataFrame({
            'feature1': np.random.randn(100),
            'feature2': np.random.randn(100) * 2,
        })
        
        df2 = df1.copy()
        
        stats = compare_feature_statistics(df1, df2)
        
        # Should return dict with statistics array
        assert isinstance(stats, dict)
        assert 'statistics' in stats
        assert 'total_columns' in stats
        
        # Find feature1 in statistics
        feature1_stats = next(s for s in stats['statistics'] if s['column'] == 'feature1')
        assert 'library_mean' in feature1_stats
        assert 'legacy_mean' in feature1_stats
        assert 'library_std' in feature1_stats
        assert 'legacy_std' in feature1_stats


class TestConsistencyValidationEdgeCases:
    """Test edge cases in consistency validation."""
    
    def test_empty_dataframes(self):
        """Test validation with empty DataFrames."""
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()
        
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        # Empty DataFrames should be considered consistent
        assert is_consistent is True
    
    def test_different_lengths(self):
        """Test validation with different length DataFrames."""
        df1 = pd.DataFrame({'feature1': [1.0, 2.0, 3.0]})
        df2 = pd.DataFrame({'feature1': [1.0, 2.0]})
        
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        # Should detect length mismatch
        assert is_consistent is False
    
    def test_different_indices(self):
        """Test validation with different indices."""
        df1 = pd.DataFrame({'feature1': [1.0, 2.0, 3.0]}, index=[0, 1, 2])
        df2 = pd.DataFrame({'feature1': [1.0, 2.0, 3.0]}, index=[10, 11, 12])
        
        # Should still compare values regardless of index
        is_consistent, diff_report = validate_feature_consistency(df1, df2, tolerance=1e-6)
        
        # Values are same, should be consistent
        assert is_consistent is True
    
    def test_tolerance_threshold(self):
        """Test that tolerance parameter works correctly."""
        df1 = pd.DataFrame({'feature1': [1.0, 2.0, 3.0]})
        df2 = pd.DataFrame({'feature1': [1.01, 2.01, 3.01]})
        
        # Should fail with tight tolerance
        is_consistent_tight, _ = validate_feature_consistency(df1, df2, tolerance=1e-6)
        assert is_consistent_tight is False
        
        # Should pass with loose tolerance
        is_consistent_loose, _ = validate_feature_consistency(df1, df2, tolerance=0.1)
        assert is_consistent_loose is True


# Fix 3: require_identical_columns=False — value-check the shared columns, report
# one-sided columns informationally (library-authoritative with opt-in lanes).

def test_relaxed_columns_pass_on_shared_agreement():
    lib = pd.DataFrame({"rsi_14": [1.0, 2.0], "dc_dir_s0": [1.0, -1.0]})  # library-only lane
    legacy = pd.DataFrame({"rsi_14": [1.0, 2.0], "price_change": [0.1, 0.2]})  # legacy-only
    ok, rep = validate_feature_consistency(lib, legacy, require_identical_columns=False)
    assert ok is True
    assert rep["column_diffs"]["missing_in_library"] == ["price_change"]
    assert rep["column_diffs"]["missing_in_legacy"] == ["dc_dir_s0"]


def test_relaxed_still_fails_on_shared_value_drift():
    lib = pd.DataFrame({"rsi_14": [1.0, 9.9], "dc_dir_s0": [1.0, -1.0]})
    legacy = pd.DataFrame({"rsi_14": [1.0, 2.0], "price_change": [0.1, 0.2]})
    ok, rep = validate_feature_consistency(lib, legacy, require_identical_columns=False)
    assert ok is False
    assert rep["error"] == "value_mismatches"


def test_strict_default_unchanged():
    lib = pd.DataFrame({"rsi_14": [1.0, 2.0], "dc_dir_s0": [1.0, -1.0]})
    legacy = pd.DataFrame({"rsi_14": [1.0, 2.0]})
    ok, rep = validate_feature_consistency(lib, legacy)  # strict default
    assert ok is False and rep["error"] == "column_mismatch"


# ── NaN-aware validation (2026-06-11): warm-up placement vs real drift ────


def test_one_sided_nan_is_informational_not_a_value_mismatch():
    """Warm-up policy difference: legacy fills the first rows where the
    library leaves NaN. Previously flagged as value_mismatch with the
    self-contradictory max_diff=0.0; now consistent + informational."""
    lib = pd.DataFrame({"volume_sma_10": [np.nan, np.nan, 3.0, 4.0]})
    legacy = pd.DataFrame({"volume_sma_10": [0.0, 0.0, 3.0, 4.0]})
    ok, rep = validate_feature_consistency(lib, legacy, tolerance=1e-6)
    assert ok is True
    assert rep["nan_placement_mismatches"] == [{
        "column": "volume_sma_10",
        "error": "nan_placement_mismatch",
        "positions": 2,
        "library_only_nan": 2,
        "legacy_only_nan": 0,
    }]


def test_real_drift_on_co_valued_rows_still_fails_with_true_diff():
    lib = pd.DataFrame({"f": [np.nan, 2.0, 3.5]})
    legacy = pd.DataFrame({"f": [0.0, 2.0, 3.0]})
    ok, rep = validate_feature_consistency(lib, legacy, tolerance=1e-6)
    assert ok is False
    (m,) = rep["mismatches"]
    assert m["error"] == "value_mismatch"
    assert m["max_diff"] == pytest.approx(0.5)  # never a 0.0 "mismatch" again
    assert rep["nan_placement_mismatches"][0]["positions"] == 1


def test_all_nan_column_on_one_side_does_not_crash():
    lib = pd.DataFrame({"f": [np.nan, np.nan]})
    legacy = pd.DataFrame({"f": [1.0, 2.0]})
    ok, rep = validate_feature_consistency(lib, legacy)
    assert ok is True  # no co-valued rows → no value evidence either way
    assert rep["nan_placement_mismatches"][0]["positions"] == 2
