"""
Benchmarking module.
Collects performance metrics including load time, inference time, RAM, and CPU usage.
"""

import time
import psutil
import numpy as np
from typing import Dict, List, Optional
from model_loader import ModelLoader


class Benchmark:
    """
    Handles benchmarking of ML models. Each benchmark run is a single
    load followed by N inference runs.
    """
    
    def __init__(self):
        """Initialize benchmarker."""
        self.process = psutil.Process()
    
    def _get_ram_usage_mb(self) -> float:
        """Get current RAM usage in MB."""
        return self.process.memory_info().rss / (1024 ** 2)
    
    def _get_cpu_percent(self) -> float:
        """Get current CPU usage percentage."""
        return self.process.cpu_percent(interval=0.1)
    
    def benchmark_load(self, model_loader: ModelLoader, model_path: str) -> Dict[str, float]:
        """
        Benchmark model loading time and RAM usage.
        
        Args:
            model_loader: ModelLoader instance
            model_path: Path to model file
            
        Returns:
            Dictionary with load time metrics and RAM usage:
            - LoadMsMin, LoadMsMax, LoadMsMedian, LoadMsAverage
            - LoadMsStdDev (optional), LoadMsFirst (optional, same as median)
            - PeakLoadRamUsage
        """
        # Measure baseline RAM
        baseline_ram = self._get_ram_usage_mb()
        
        # Single load - reflects real usage where models are loaded on-demand
        start_time = time.perf_counter()
        model_loader.load_model(model_path)
        load_time_ms = (time.perf_counter() - start_time) * 1000
        
        peak_ram = self._get_ram_usage_mb() - baseline_ram
        
        # For single load, all statistics are the same value
        return {
            'LoadMsMedian': float(load_time_ms),
            'LoadMsMin': float(load_time_ms),
            'LoadMsMax': float(load_time_ms),
            'LoadMsAverage': float(load_time_ms),
            'LoadMsStdDev': 0.0,  # Single measurement has no variance
            'LoadMsFirst': float(load_time_ms),  # Optional: first/only load
            'PeakLoadRamUsage': float(peak_ram),
        }
    
    def benchmark_inference(self, model_loader: ModelLoader, num_runs: int = 10) -> Dict[str, float]:
        """
        Benchmark inference time and RAM usage.
        
        Args:
            model_loader: ModelLoader instance with loaded model
            num_runs: Number of inference runs to perform
            
        Returns:
            Dictionary with inference time metrics and peak RAM usage:
            - InferenceMsMin, InferenceMsMax, InferenceMsMedian, InferenceMsAverage
            - InferenceMsStdDev (optional), InferenceMsFirst (optional)
            - PeakInferenceRamUsage
        """
        if model_loader.session is None:
            raise ValueError("Model not loaded. Call benchmark_load() first.")
        
        # Measure baseline RAM
        baseline_ram = self._get_ram_usage_mb()
        
        # Prepare input (auto-generated from model signature)
        input_data = model_loader.create_input()
        
        inference_times = []
        ram_usage_during_inference = []
        
        for _ in range(num_runs):
            start_time = time.perf_counter()
            _ = model_loader.run_inference(input_data)
            inference_time_ms = (time.perf_counter() - start_time) * 1000
            
            ram_usage = self._get_ram_usage_mb() - baseline_ram
            
            inference_times.append(inference_time_ms)
            ram_usage_during_inference.append(ram_usage)
        
        # Calculate statistics from all runs
        if len(inference_times) > 0:
            times_array = np.array(inference_times)
            return {
                'InferenceMsMedian': float(np.median(times_array)),
                'InferenceMsMin': float(np.min(times_array)),
                'InferenceMsMax': float(np.max(times_array)),
                'InferenceMsAverage': float(np.mean(times_array)),
                'InferenceMsStdDev': float(np.std(times_array)) if len(times_array) > 1 else 0.0,
                'InferenceMsFirst': float(inference_times[0]),  # Optional: first run
                'PeakInferenceRamUsage': float(max(ram_usage_during_inference)),
            }
        else:
            raise ValueError("No inference runs completed")
    
    def run_full_benchmark(self, model_loader: ModelLoader, model_path: str, 
                          num_inference_runs: int = 10) -> Dict[str, float]:
        """
        Run complete benchmark: single load + N inference runs (real usage pattern).
        
        Args:
            model_loader: ModelLoader instance
            model_path: Path to model file
            num_inference_runs: Number of inference runs to measure
            
        Returns:
            Dictionary with all benchmark metrics (min, max, median, mean, etc.)
        """
        # Benchmark loading (single load)
        load_metrics = self.benchmark_load(model_loader, model_path)
        
        # Benchmark inference (all runs measured)
        inference_metrics = self.benchmark_inference(model_loader, num_inference_runs)
        
        # Combine metrics
        return {**load_metrics, **inference_metrics}

