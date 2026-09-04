"""
Pytest configuration and fixtures for VDMC core library tests.
"""

import numpy as np
import pytest

from vdmc_core import SignalType, VDMCConfig


@pytest.fixture
def default_config():
    """Default VDMC configuration for testing."""
    return VDMCConfig()


@pytest.fixture
def buy_signal_config():
    """VDMC configuration for buy signals."""
    return VDMCConfig(signal_type=SignalType.BUY)


@pytest.fixture
def sell_signal_config():
    """VDMC configuration for sell signals."""
    return VDMCConfig(signal_type=SignalType.SELL)


@pytest.fixture
def short_history_config():
    """VDMC configuration with short lookback period."""
    return VDMCConfig(lookback_period=120)


@pytest.fixture
def sample_price_data():
    """Generate sample price data for testing."""
    np.random.seed(42)  # For reproducible tests
    base_price = 1000.0
    trend = np.linspace(0, 50, 200)
    noise = np.random.normal(0, 10, 200)
    volatility = np.sin(np.linspace(0, 4 * np.pi, 200)) * 20
    
    prices = base_price + trend + noise + volatility
    return prices


@pytest.fixture
def long_price_data():
    """Generate long price series for performance testing."""
    np.random.seed(42)
    base_price = 1000.0
    trend = np.linspace(0, 100, 720)
    noise = np.random.normal(0, 15, 720)
    volatility = np.sin(np.linspace(0, 8 * np.pi, 720)) * 25
    
    prices = base_price + trend + noise + volatility
    return prices


@pytest.fixture
def short_price_data():
    """Generate short price series for fallback testing."""
    return np.array([100.0, 101.0, 102.0, 103.0, 104.0])


@pytest.fixture
def nan_price_data():
    """Generate price data with NaN values."""
    data = np.array([100.0, 101.0, np.nan, 103.0, 104.0] + [105.0] * 195)
    return data


@pytest.fixture
def inf_price_data():
    """Generate price data with infinite values."""
    data = np.array([100.0, 101.0, np.inf, 103.0, 104.0] + [105.0] * 195)
    return data


@pytest.fixture
def golden_test_data():
    """
    Golden test data with manually calculated expected results.
    
    This data was generated using the scripts/generate_golden_values.py script
    which manually calculates each step of the VDMC algorithm for verification.
    
    The expected values are mathematically verified and serve as the ground truth
    for testing the VDMC implementation correctness.
    
    Price series: 150 points with base price + linear trend + sine wave pattern
    Configuration: default VDMCConfig (sigma=5, alpha=1.2, beta=0.8, signal_type=BUY)
    """
    # Golden values generated and verified manually with 150-point dataset
    prices = np.array([
        100.0, 100.29512071948498, 100.5898666750896, 100.88386376925001, 
        101.17673923585068, 101.46812230298892, 101.75764485219388, 102.04494207292765, 
        102.32965311120516, 102.61142171117935, 102.88989684855109, 103.16473335467758, 
        103.43559253026959, 103.7021427475864, 103.9640600400579, 104.2210286782853, 
        104.47274173139638, 104.71890161275758, 104.95922060907193, 105.19342139192305, 
        105.42123751085474, 105.64241386711028, 105.85670716718869, 106.06388635541167, 
        106.2637330247322, 106.4560418050543, 106.64062072837349, 106.81729157008901, 
        106.9858901658806, 107.14626670358665, 107.29828598956476, 107.44182768906118, 
        107.5767865401615, 107.70307254094257, 107.8206111094926, 107.9293432165151, 
        108.02922549028075, 108.12023029374089, 108.20234577366502, 108.27557588171555, 
        108.33994036742178, 108.39547474306603, 108.44223022054405, 108.4802736203122, 
        108.50968725258303, 108.53056877098082, 108.54303099891693, 108.54720172899391, 
        108.54322349579493, 108.5312533224625, 108.51146244151701, 108.48403599041158, 
        108.44917268236449, 108.4070844530542, 108.35799608380553, 108.30214480193669, 
        108.2397798589777, 108.17116208751028, 108.09656343741712, 108.01626649236476, 
        107.9305639673803, 107.83975818841463, 107.74416055481807, 107.64409098568349, 
        107.53987735104208, 107.43185488892217, 107.32036560930841, 107.20575768606041, 
        107.08838483787237, 106.9686056993741, 106.84678318349182, 106.72328383620214, 
        106.5984771848267, 106.47273508102617, 106.3464310396614, 106.21993957469778, 
        106.093635533333, 105.96789342953247, 105.84308677815703, 105.71958743086735, 
        105.59776491498508, 105.47798577648682, 105.36061292829876, 105.24600500505076, 
        105.134515725437, 105.0264932633171, 104.92227962867568, 104.82221005954112, 
        104.72661242594454, 104.63580664697888, 104.55010412199441, 104.46980717694206, 
        104.39520852684889, 104.32659075538147, 104.26422581242248, 104.20837453055364, 
        104.15928616130498, 104.11719793199468, 104.08233462394759, 104.05490817284218, 
        104.03511729189667, 104.02314711856424, 104.01916888536526, 104.02333961544224, 
        104.03580184337835, 104.05668336177614, 104.08609699404698, 104.12414039381513, 
        104.17089587129314, 104.2264302469374, 104.29079473264362, 104.36402484069414, 
        104.4461403206183, 104.53714512407842, 104.63702739784408, 104.74575950486657, 
        104.8632980734166, 104.98958407419767, 105.12454292529799, 105.26808462479441, 
        105.42010391077253, 105.58048044847857, 105.74907904427016, 105.92574988598568, 
        106.11032880930487, 106.30263758962697, 106.5024842589475, 106.70966344717048, 
        106.9239567472489, 107.14513310350443, 107.37294922243612, 107.60715000528724, 
        107.84746900160161, 108.09362888296279, 108.34534193607388, 108.60231057430127, 
        108.86422786677277, 109.1307780840896, 109.40163725968159, 109.67647376580808, 
        109.95494890317983, 110.23671750315401, 110.52142854143152, 110.8087257621653, 
        111.09824831137026, 111.3896313785085, 111.68250684510916, 111.97650393926958, 
        112.2712498948742, 112.56637061435917
    ])
    
    # Expected outputs calculated manually and verified
    # Generated by manual_vdmc_calculation() in scripts/generate_golden_values.py
    expected_results = {
        'p_buy': 0.5057130185499209,
        'p_sell': 0.49428698145007904,
        'wave_amplitude': 0.03942967458758536,
        'momentum': 0.04533067368890897
    }
    
    return {
        'prices': prices,
        'expected': expected_results
    } 