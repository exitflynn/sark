"""
Device information detection module.
Collects hardware and OS information for benchmarking reports.
"""

import platform
import psutil
import sys
import uuid
import subprocess
from typing import Dict, Optional


def get_device_udid() -> str:
    """
    Get unique device identifier (UDID).
    
    For macOS: Uses hardware UUID
    For Linux: Uses machine ID or generates from hostname
    For Windows: Uses UUID from registry or generates
    
    Returns:
        Unique device identifier string
    """
    system = platform.system()
    
    # macOS: Get hardware UUID
    if system == "Darwin":
        try:
            result = subprocess.run(
                ['system_profiler', 'SPHardwareDataType'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Hardware UUID' in line:
                        udid = line.split(':')[-1].strip()
                        if udid:
                            return udid
        except:
            pass
        
        # Fallback: Try ioreg
        try:
            result = subprocess.run(
                ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and 'IOPlatformUUID' in result.stdout:
                for line in result.stdout.split('\n'):
                    if 'IOPlatformUUID' in line:
                        udid = line.split('=')[-1].strip().strip('"')
                        if udid:
                            return udid
        except:
            pass
    
    # Linux: Get machine ID
    elif system == "Linux":
        try:
            with open('/etc/machine-id', 'r') as f:
                udid = f.read().strip()
                if udid:
                    return udid
        except:
            pass
    
    # Windows or fallback: Use UUID based on hostname + MAC address
    try:
        hostname = platform.node()
        mac_address = uuid.getnode()
        udid = f"{hostname}_{mac_address}"
        return udid
    except:
        pass
    
    # Last resort: Generate UUID
    return str(uuid.uuid4())


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
    
    # Get device UDID
    device_udid = get_device_udid()
    
    return {
        'DeviceName': device_name,
        'DeviceYear': device_year,
        'Soc': cpu_info,
        'Ram': int(ram_gb),
        'DiscreteGpu': discrete_gpu,
        'VRam': vram,
        'DeviceOs': system,
        'DeviceOsVersion': os_version,
        'UDID': device_udid,
    }


def get_compute_units() -> list:
    """
    Get available compute units for inference.
    
    Returns:
        List of available compute unit strings (e.g., ['CPU', 'GPU', 'NEURAL_ENGINE', 'CoreML'])
    """
    units = ['CPU']  # CPU is always available
    
    system = platform.system()
    
    # Check for CoreML and Apple Silicon on macOS
    if system == "Darwin":
        # Check if CoreML tools are available
        try:
            import coremltools
            units.append('CoreML')
        except ImportError:
            pass
        
        # Detect Apple Silicon and GPU/Neural Engine
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'machdep.cpu.brand_string'],
                capture_output=True, text=True, timeout=2
            )
            cpu_info = result.stdout.strip() if result.returncode == 0 else ""
            
            # Apple Silicon detection (M1, M1 Pro, M1 Max, M2, M2 Pro, M2 Max, M3, etc.)
            if 'Apple' in cpu_info:
                # All Apple Silicon chips have GPU and Neural Engine
                if 'GPU' not in units:
                    units.append('GPU')
                if 'NEURAL_ENGINE' not in units:
                    units.append('NEURAL_ENGINE')
        except Exception:
            pass
    
    # Check for ONNX Runtime providers
    try:
        import onnxruntime as ort
        available_providers = ort.get_available_providers()
        
        if 'DmlExecutionProvider' in available_providers:
            if 'DML' not in units:
                units.append('DML')
        if 'OpenVINOExecutionProvider' in available_providers:
            if 'OpenVINO;CPU' not in units:
                units.append('OpenVINO;CPU')
            # Check if GPU is available for OpenVINO
            if 'OpenVINOExecutionProvider' in available_providers:
                # This is a simplified check - in practice, you'd check device availability
                if 'OpenVINO;GPU' not in units:
                    units.append('OpenVINO;GPU')
        
        # CoreML support via ONNX Runtime (if available)
        if 'CoreMLExecutionProvider' in available_providers:
            if 'CoreML' not in units:
                units.append('CoreML')
    except ImportError:
        pass
    
    return units

