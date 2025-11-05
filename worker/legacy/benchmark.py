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
    """Handles benchmarking of ML models."""
    
    def __init__(self, num_warmups: int = 5):
        """
        Initialize benchmarker.
        
        Args:
            num_warmups: Number of warmup runs before actual benchmarking
        """
        self.num_warmups = num_warmups
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
            Dictionary with load time metrics and peak RAM usage
        """
        # Measure baseline RAM
        baseline_ram = self._get_ram_usage_mb()
        
        # Measure load time
        load_times = []
        ram_usage_during_load = []
        
        for i in range(self.num_warmups + 1):
            # Clear previous session
            if model_loader.session is not None:
                model_loader.session = None
            
            start_time = time.perf_counter()
            model_loader.load_model(model_path)
            load_time_ms = (time.perf_counter() - start_time) * 1000
            
            ram_usage = self._get_ram_usage_mb() - baseline_ram
            ram_usage_during_load.append(ram_usage)
            
            if i == 0:
                # First run (cold start)
                load_first = load_time_ms
            else:
                load_times.append(load_time_ms)
        
        # Calculate statistics
        if len(load_times) > 0:
            load_times_array = np.array(load_times)
            return {
                'LoadMsMedian': float(np.median(load_times_array)),
                'LoadMsStdDev': float(np.std(load_times_array)) if len(load_times_array) > 1 else 0.0,
                'LoadMsAverage': float(np.mean(load_times_array)),
                'LoadMsFirst': float(load_first),
                'PeakLoadRamUsage': float(max(ram_usage_during_load)),
            }
        else:
            # Edge case: only one run
            return {
                'LoadMsMedian': float(load_first),
                'LoadMsStdDev': 0.0,
                'LoadMsAverage': float(load_first),
                'LoadMsFirst': float(load_first),
                'PeakLoadRamUsage': float(max(ram_usage_during_load)),
            }
    
    def benchmark_inference(self, model_loader: ModelLoader, num_runs: int = 10) -> Dict[str, float]:
        """
        Benchmark inference time and RAM usage.
        
        Args:
            model_loader: ModelLoader instance with loaded model
            num_runs: Number of inference runs to perform
            
        Returns:
            Dictionary with inference time metrics and peak RAM usage
        """
        if model_loader.session is None:
            raise ValueError("Model not loaded. Call benchmark_load() first.")
        
        # Measure baseline RAM
        baseline_ram = self._get_ram_usage_mb()
        
        # Prepare input
        input_data = model_loader.create_input()
        
        # Warmup runs
        for _ in range(self.num_warmups):
            _ = model_loader.run_inference(input_data)
        
        # Actual benchmark runs
        inference_times = []
        ram_usage_during_inference = []
        
        for i in range(num_runs):
            # Measure RAM before inference
            ram_before = self._get_ram_usage_mb()
            
            start_time = time.perf_counter()
            _ = model_loader.run_inference(input_data)
            inference_time_ms = (time.perf_counter() - start_time) * 1000
            
            ram_after = self._get_ram_usage_mb()
            ram_usage = ram_after - baseline_ram
            
            if i == 0:
                # First run
                inference_first = inference_time_ms
            else:
                inference_times.append(inference_time_ms)
            
            ram_usage_during_inference.append(ram_usage)
        
        # Calculate statistics
        if len(inference_times) > 0:
            inference_times_array = np.array(inference_times)
            return {
                'InferenceMsMedian': float(np.median(inference_times_array)),
                'InferenceMsStdDev': float(np.std(inference_times_array)) if len(inference_times_array) > 1 else 0.0,
                'InferenceMsAverage': float(np.mean(inference_times_array)),
                'InferenceMsFirst': float(inference_first),
                'PeakInferenceRamUsage': float(max(ram_usage_during_inference)),
            }
        else:
            # Edge case: only one run
            return {
                'InferenceMsMedian': float(inference_first),
                'InferenceMsStdDev': 0.0,
                'InferenceMsAverage': float(inference_first),
                'InferenceMsFirst': float(inference_first),
                'PeakInferenceRamUsage': float(max(ram_usage_during_inference)),
            }
    
    def run_full_benchmark(self, model_loader: ModelLoader, model_path: str, 
                          num_inference_runs: int = 10) -> Dict[str, float]:
        """
        Run complete benchmark including load and inference.
        
        Args:
            model_loader: ModelLoader instance
            model_path: Path to model file
            num_inference_runs: Number of inference runs to perform
            
        Returns:
            Dictionary with all benchmark metrics
        """
        # Benchmark loading
        load_metrics = self.benchmark_load(model_loader, model_path)
        
        # Benchmark inference
        inference_metrics = self.benchmark_inference(model_loader, num_inference_runs)
        
        # Combine metrics
        return {**load_metrics, **inference_metrics}

