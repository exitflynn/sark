"""
Main worker/agent script.
Runs benchmarking on a single machine and generates CSV reports.
"""

import os
import sys
import argparse
import csv
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

from device_info import get_device_info, get_compute_units
from model_loader import ModelLoader
from benchmark import Benchmark


def generate_upload_id() -> str:
    """Generate a unique upload ID."""
    import hashlib
    import random
    return hashlib.md5(f"{datetime.now()}{random.random()}".encode()).hexdigest()


def run_benchmark_job(model_url: str, compute_unit: str = 'CPU', 
                     num_inference_runs: int = 10) -> Dict:
    """
    Run a single benchmark job.
    
    Args:
        model_url: URL to download the model from
        compute_unit: Compute unit to use for inference
        num_inference_runs: Number of inference runs to measure (all measured)
        
    Returns:
        Dictionary with benchmark results
    """
    print(f"\n{'='*60}")
    print(f"Starting benchmark for {model_url}")
    print(f"Compute Unit: {compute_unit}")
    print(f"{'='*60}\n")
    
    # Initialize components
    model_loader = ModelLoader(compute_unit=compute_unit)
    benchmark = Benchmark()
    
    try:
        # Download model
        model_path = model_loader.download_model(model_url)
        
        # Run benchmark
        metrics = benchmark.run_full_benchmark(
            model_loader, 
            model_path, 
            num_inference_runs=num_inference_runs
        )
        
        # Get model file info
        file_size = os.path.getsize(model_path)
        filename = os.path.basename(model_path)
        
        # Cleanup
        model_loader.cleanup()
        
        return {
            'Status': 'Complete',
            'FileName': filename,
            'FileSize': file_size,
            'ComputeUnits': compute_unit,
            **metrics
        }
    
    except Exception as e:
        print(f"Error during benchmark: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'Status': 'Failed',
            'FileName': os.path.basename(model_url) if model_url else 'unknown',
            'FileSize': 0,
            'ComputeUnits': compute_unit,
            'remark': str(e)
        }


def generate_csv_report(results: list, output_path: str):
    """
    Generate CSV report from benchmark results.
    
    Args:
        results: List of benchmark result dictionaries
        output_path: Path to output CSV file
    """
    if not results:
        print("No results to write.")
        return
    
    # Get device info (assuming all results are from same device)
    device_info = get_device_info()
    
    # CSV columns matching the sample format
    fieldnames = [
        'CreatedUtc', 'Status', 'UploadId', 'FileName', 'FileSize', 'CompressionConfig',
        'DeviceName', 'DeviceYear', 'Soc', 'Ram', 'DiscreteGpu', 'VRam',
        'DeviceOs', 'DeviceOsVersion', 'ComputeUnits',
        'LoadMsMin', 'LoadMsMax', 'LoadMsMedian', 'LoadMsStdDev', 'LoadMsAverage', 'LoadMsFirst', 'PeakLoadRamUsage',
        'InferenceMsMin', 'InferenceMsMax', 'InferenceMsMedian', 'InferenceMsStdDev', 'InferenceMsAverage', 'InferenceMsFirst', 'PeakInferenceRamUsage'
    ]
    
    upload_id = generate_upload_id()
    created_utc = datetime.utcnow().isoformat()
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            # Helper function to convert None to empty string
            def safe_value(val):
                return '' if val is None else val
            
            row = {
                'CreatedUtc': created_utc,
                'Status': result.get('Status', 'Unknown'),
                'UploadId': upload_id,
                'FileName': safe_value(result.get('FileName')),
                'FileSize': safe_value(result.get('FileSize', 0)),
                'CompressionConfig': 'original',
                'DeviceName': safe_value(device_info.get('DeviceName')),
                'DeviceYear': safe_value(device_info.get('DeviceYear')),
                'Soc': safe_value(device_info.get('Soc')),
                'Ram': safe_value(device_info.get('Ram')),
                'DiscreteGpu': safe_value(device_info.get('DiscreteGpu')),
                'VRam': safe_value(device_info.get('VRam')),
                'DeviceOs': safe_value(device_info.get('DeviceOs')),
                'DeviceOsVersion': safe_value(device_info.get('DeviceOsVersion')),
                'ComputeUnits': safe_value(result.get('ComputeUnits')),
                'LoadMsMin': safe_value(result.get('LoadMsMin')),
                'LoadMsMax': safe_value(result.get('LoadMsMax')),
                'LoadMsMedian': safe_value(result.get('LoadMsMedian')),
                'LoadMsStdDev': safe_value(result.get('LoadMsStdDev')),
                'LoadMsAverage': safe_value(result.get('LoadMsAverage')),
                'LoadMsFirst': safe_value(result.get('LoadMsFirst')),
                'PeakLoadRamUsage': safe_value(result.get('PeakLoadRamUsage')),
                'InferenceMsMin': safe_value(result.get('InferenceMsMin')),
                'InferenceMsMax': safe_value(result.get('InferenceMsMax')),
                'InferenceMsMedian': safe_value(result.get('InferenceMsMedian')),
                'InferenceMsStdDev': safe_value(result.get('InferenceMsStdDev')),
                'InferenceMsAverage': safe_value(result.get('InferenceMsAverage')),
                'InferenceMsFirst': safe_value(result.get('InferenceMsFirst')),
                'PeakInferenceRamUsage': safe_value(result.get('PeakInferenceRamUsage')),
            }
            writer.writerow(row)
    
    print(f"\nCSV report generated: {output_path}")


def main():
    """Main entry point for the worker."""
    parser = argparse.ArgumentParser(
        description='ML Model Benchmarking Worker - Single Machine Prototype'
    )
    parser.add_argument(
        '--model-url',
        type=str,
        required=True,
        help='URL to download the ONNX model from, or local file path'
    )
    parser.add_argument(
        '--compute-unit',
        type=str,
        default='CPU',
        help='Compute unit to use (CPU, DML, OpenVINO;CPU, etc.)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='benchmark_results.csv',
        help='Output CSV file path'
    )
    parser.add_argument(
        '--num-inference-runs',
        type=int,
        default=10,
        help='Number of inference runs to measure'
    )
    parser.add_argument(
        '--all-compute-units',
        action='store_true',
        help='Run benchmark on all available compute units'
    )
    
    args = parser.parse_args()
    
    # Get available compute units
    available_units = get_compute_units()
    print(f"Available compute units: {available_units}")
    
    # Determine which compute units to test
    if args.all_compute_units:
        compute_units_to_test = available_units
    else:
        if args.compute_unit not in available_units:
            print(f"Warning: {args.compute_unit} not available. Using CPU instead.")
            compute_units_to_test = ['CPU']
        else:
            compute_units_to_test = [args.compute_unit]
    
    # Run benchmarks
    results = []
    for compute_unit in compute_units_to_test:
        result = run_benchmark_job(
            model_url=args.model_url,
            compute_unit=compute_unit,
            num_inference_runs=args.num_inference_runs
        )
        results.append(result)
    
    # Generate CSV report
    generate_csv_report(results, args.output)
    
    print("\nBenchmarking complete!")


if __name__ == '__main__':
    main()

