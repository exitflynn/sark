"""
Device information detection module.
Collects hardware and OS information for benchmarking reports.
"""

import platform
import psutil
import sys
from typing import Dict, Optional


def get_device_info() -> Dict[str, Optional[str]]:
    """
    Collect device information including hardware specs and OS details.
    
    Returns:
        Dictionary containing device information
    """
    # System information
    system = platform.system()
    os_version = platform.version()
    
    # Processor information
    processor = platform.processor()
    
    # RAM information
    ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    
    # Try to get more detailed CPU info
    cpu_info = processor
    if hasattr(platform, 'mac_ver'):
        # macOS
        try:
            import subprocess
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                cpu_info = result.stdout.strip()
        except:
            pass
    
    # GPU information (basic detection)
    discrete_gpu = None
    vram = None
    
    # Try to detect GPU on macOS
    if system == "Darwin":
        try:
            import subprocess
            result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and "Chipset Model" in result.stdout:
                # Extract GPU info if available
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if "Chipset Model" in line:
                        discrete_gpu = line.split(':')[-1].strip() if ':' in line else None
                        break
        except:
            pass
    
    # Device name (hostname)
    device_name = platform.node()
    
    # Try to get model name on macOS
    if system == "Darwin":
        try:
            import subprocess
            result = subprocess.run(['sysctl', '-n', 'hw.model'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                device_name = result.stdout.strip()
        except:
            pass
    
    # Device year (not easily detectable, will be None)
    device_year = None
    
    return {
        'DeviceName': device_name,
        'DeviceYear': device_year,
        'Soc': cpu_info,
        'Ram': int(ram_gb),
        'DiscreteGpu': discrete_gpu,
        'VRam': vram,
        'DeviceOs': system,
        'DeviceOsVersion': os_version,
    }


def get_compute_units() -> list:
    """
    Get available compute units for inference.
    
    Returns:
        List of available compute unit strings (e.g., ['CPU', 'DML', 'OpenVINO;CPU'])
    """
    units = ['CPU']  # CPU is always available
    
    # Check for ONNX Runtime providers
    try:
        import onnxruntime as ort
        available_providers = ort.get_available_providers()
        
        if 'DmlExecutionProvider' in available_providers:
            units.append('DML')
        if 'OpenVINOExecutionProvider' in available_providers:
            units.append('OpenVINO;CPU')
            # Check if GPU is available for OpenVINO
            if 'OpenVINOExecutionProvider' in available_providers:
                # This is a simplified check - in practice, you'd check device availability
                units.append('OpenVINO;GPU')
    except:
        pass
    
    return units

