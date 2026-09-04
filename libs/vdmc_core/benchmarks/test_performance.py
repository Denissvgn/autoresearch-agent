"""
Performance benchmark tests for VDMC core library.

This module contains performance tests to ensure the VDMC calculation
meets the ≤20ms p95 latency requirement specified in the technical specification.
"""

from statistics import mean, stdev
import time

import numpy as np
import pytest

from vdmc_core import VDMCConfig, vdmc


@pytest.mark.benchmark
class TestVDMCPerformance:
    """Performance benchmark tests for VDMC algorithm."""
    
    def test_vdmc_latency_requirement(self):
        """Test that VDMC meets the ≤20ms p95 latency requirement."""
        # Generate test data at maximum lookback period
        np.random.seed(42)
        close_prices = np.random.randn(720) * 100 + 1000  # Max lookback period
        config = VDMCConfig()
        
        # Warm up runs to stabilize performance
        for _ in range(10):
            vdmc(close_prices, config)
        
        # Benchmark runs
        times = []
        num_runs = 100
        
        for _ in range(num_runs):
            start = time.perf_counter()
            result = vdmc(close_prices, config)
            end = time.perf_counter()
            
            # Verify result is valid
            assert 0.0 <= result.p_buy <= 1.0
            assert 0.0 <= result.p_sell <= 1.0
            
            times.append((end - start) * 1000)  # Convert to milliseconds
        
        # Calculate statistics
        mean_latency = mean(times)
        std_latency = stdev(times)
        p95_latency = np.percentile(times, 95)
        p99_latency = np.percentile(times, 99)
        max_latency = max(times)
        
        print("\n📊 VDMC Performance Statistics:")
        print(f"   Mean latency: {mean_latency:.2f}ms")
        print(f"   Std deviation: {std_latency:.2f}ms")
        print(f"   P95 latency: {p95_latency:.2f}ms")
        print(f"   P99 latency: {p99_latency:.2f}ms")
        print(f"   Max latency: {max_latency:.2f}ms")
        
        # Verify requirement
        assert p95_latency <= 20.0, f"P95 latency {p95_latency:.2f}ms exceeds 20ms requirement"
    
    def test_vdmc_different_data_sizes(self):
        """Test performance with different data sizes."""
        config = VDMCConfig()
        data_sizes = [120, 240, 360, 480, 600, 720]
        
        for size in data_sizes:
            np.random.seed(42)
            close_prices = np.random.randn(size) * 100 + 1000
            
            # Quick performance check
            times = []
            for _ in range(10):
                start = time.perf_counter()
                result = vdmc(close_prices, config)
                end = time.perf_counter()
                times.append((end - start) * 1000)
                
                # Verify result
                assert 0.0 <= result.p_buy <= 1.0
                assert 0.0 <= result.p_sell <= 1.0
            
            avg_time = mean(times)
            print(f"Data size {size}: {avg_time:.2f}ms average")
            
            # Even largest size should be reasonable
            assert avg_time <= 25.0, f"Average time for size {size} exceeds reasonable limit"
    
    def test_vdmc_scalability_with_data_size(self):
        """Test VDMC performance with different data sizes."""
        config = VDMCConfig()
        data_sizes = [120, 240, 360, 480, 600, 720]  # Different history lengths
        
        results = {}
        
        for size in data_sizes:
            np.random.seed(42)
            close_prices = np.random.randn(size) * 100 + 1000
            
            # Warm up
            for _ in range(5):
                vdmc(close_prices, config)
            
            # Benchmark
            times = []
            for _ in range(20):
                start = time.perf_counter()
                vdmc(close_prices, config)
                end = time.perf_counter()
                times.append((end - start) * 1000)
            
            avg_time = mean(times)
            results[size] = avg_time
            
            print(f"Data size {size}: {avg_time:.2f}ms average")
        
        # Performance should scale reasonably with data size
        # but shouldn't exceed 20ms even for largest size
        assert results[720] <= 20.0, "Performance with max data size exceeds requirement"
    
    def test_vdmc_parameter_impact_on_performance(self):
        """Test performance impact of different parameter configurations."""
        np.random.seed(42)
        close_prices = np.random.randn(720) * 100 + 1000
        
        configurations = [
            ("default", VDMCConfig()),
            ("high_sigma", VDMCConfig(kernel_sigma=21)),
            ("low_sigma", VDMCConfig(kernel_sigma=3)),
            ("extreme_alpha_beta", VDMCConfig(alpha=10.0, beta=10.0)),
        ]
        
        for config_name, config in configurations:
            # Warm up
            for _ in range(5):
                vdmc(close_prices, config)
            
            # Benchmark
            times = []
            for _ in range(30):
                start = time.perf_counter()
                vdmc(close_prices, config)
                end = time.perf_counter()
                times.append((end - start) * 1000)
            
            avg_time = mean(times)
            p95_time = np.percentile(times, 95)
            
            print(f"{config_name}: avg={avg_time:.2f}ms, p95={p95_time:.2f}ms")
            
            # All configurations should meet performance requirement
            assert p95_time <= 20.0, f"{config_name} P95 latency exceeds requirement"
    
    def test_vdmc_memory_efficiency(self):
        """Test memory usage of VDMC calculation."""
        import tracemalloc
        
        np.random.seed(42)
        close_prices = np.random.randn(720) * 100 + 1000
        config = VDMCConfig()
        
        # Start memory tracing
        tracemalloc.start()
        
        # Run VDMC calculation
        result = vdmc(close_prices, config)
        
        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print("\n💾 Memory Usage:")
        print(f"   Current: {current / 1024:.2f} KB")
        print(f"   Peak: {peak / 1024:.2f} KB")
        
        # Verify result is valid
        assert isinstance(result.p_buy, float)
        assert isinstance(result.p_sell, float)
        
        # Memory usage should be reasonable (less than 10MB for this calculation)
        assert peak < 10 * 1024 * 1024, f"Memory usage {peak / 1024 / 1024:.2f}MB is too high"
    
    def test_vdmc_concurrent_execution(self):
        """Test VDMC performance under concurrent execution."""
        import concurrent.futures
        
        np.random.seed(42)
        close_prices = np.random.randn(720) * 100 + 1000
        config = VDMCConfig()
        
        def run_vdmc():
            """Single VDMC execution for threading test."""
            start = time.perf_counter()
            result = vdmc(close_prices, config)
            end = time.perf_counter()
            return (end - start) * 1000, result
        
        # Test with multiple concurrent executions
        num_threads = 4
        num_runs_per_thread = 10
        
        all_times = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            
            for _ in range(num_threads * num_runs_per_thread):
                future = executor.submit(run_vdmc)
                futures.append(future)
            
            for future in concurrent.futures.as_completed(futures):
                exec_time, result = future.result()
                all_times.append(exec_time)
                
                # Verify result validity
                assert 0.0 <= result.p_buy <= 1.0
                assert 0.0 <= result.p_sell <= 1.0
        
        # Calculate concurrent performance statistics
        mean_concurrent = mean(all_times)
        p95_concurrent = np.percentile(all_times, 95)
        
        print("\n🔀 Concurrent Execution Statistics:")
        print(f"   Threads: {num_threads}")
        print(f"   Total runs: {len(all_times)}")
        print(f"   Mean latency: {mean_concurrent:.2f}ms")
        print(f"   P95 latency: {p95_concurrent:.2f}ms")
        
        # Performance under concurrency should still meet requirements
        assert p95_concurrent <= 25.0, f"Concurrent P95 latency {p95_concurrent:.2f}ms exceeds reasonable limit"


@pytest.mark.benchmark
def test_vdmc_stress_test():
    """Stress test VDMC with continuous execution."""
    np.random.seed(42)
    close_prices = np.random.randn(720) * 100 + 1000
    config = VDMCConfig()
    
    # Run for extended period
    duration_seconds = 5
    start_time = time.time()
    execution_count = 0
    times = []
    
    while time.time() - start_time < duration_seconds:
        exec_start = time.perf_counter()
        result = vdmc(close_prices, config)
        exec_end = time.perf_counter()
        
        times.append((exec_end - exec_start) * 1000)
        execution_count += 1
        
        # Verify result validity
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0
    
    # Calculate stress test statistics
    executions_per_second = execution_count / duration_seconds
    mean_latency = mean(times)
    p95_latency = np.percentile(times, 95)
    
    print("\n⚡ Stress Test Results:")
    print(f"   Duration: {duration_seconds}s")
    print(f"   Total executions: {execution_count}")
    print(f"   Executions/second: {executions_per_second:.1f}")
    print(f"   Mean latency: {mean_latency:.2f}ms")
    print(f"   P95 latency: {p95_latency:.2f}ms")
    
    # Should maintain performance under stress
    assert p95_latency <= 20.0, f"Stress test P95 latency {p95_latency:.2f}ms exceeds requirement"
    assert executions_per_second >= 10, f"Throughput {executions_per_second:.1f} exec/s too low" 