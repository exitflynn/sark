#!/usr/bin/env python3
"""
CycleOPS Setup Validation & Diagnostics Script

Validates the setup of a worker or orchestrator node.
Identifies missing dependencies, platform issues, and configuration problems.

Usage:
    python3 setup_validation.py --mode worker
    python3 setup_validation.py --mode orchestrator
    python3 setup_validation.py --mode full-check
"""

import sys
import os
import platform
import subprocess
import json
import socket
from pathlib import Path
from typing import Dict, Tuple, List, Any
import argparse


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")


def print_check(name: str, passed: bool, message: str = ""):
    """Print a check result."""
    status = f"{Colors.GREEN}✅{Colors.RESET}" if passed else f"{Colors.RED}❌{Colors.RESET}"
    print(f"  {status} {name:50} {message}")


def print_section(title: str):
    """Print a section title."""
    print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{'-'*70}")


def run_command(cmd: List[str], shell: bool = False) -> Tuple[bool, str]:
    """
    Run a command and return success status and output.
    
    Args:
        cmd: Command as list of strings
        shell: If True, run as shell command
        
    Returns:
        (success: bool, output: str)
    """
    try:
        if shell:
            result = subprocess.run(
                ' '.join(cmd),
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "Command not found"
    except Exception as e:
        return False, str(e)


def check_python() -> Dict[str, Any]:
    """Check Python environment."""
    results = {}
    
    # Python version
    version_info = sys.version_info
    python_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    results['version'] = python_version
    results['version_ok'] = version_info >= (3, 8)
    
    # Python path
    results['executable'] = sys.executable
    results['prefix'] = sys.prefix
    
    return results


def check_platform() -> Dict[str, Any]:
    """Check platform information."""
    results = {}
    
    system = platform.system()
    results['system'] = system
    results['release'] = platform.release()
    results['version'] = platform.version()
    results['machine'] = platform.machine()
    results['processor'] = platform.processor()
    
    # macOS specific
    if system == "Darwin":
        success, output = run_command(['sw_vers', '-productVersion'])
        if success:
            results['macos_version'] = output
        
        success, output = run_command(['sysctl', '-n', 'hw.model'])
        if success:
            results['mac_model'] = output
    
    # Windows specific
    if system == "Windows":
        success, output = run_command(['wmic', 'os', 'get', 'version'])
        if success:
            results['windows_info'] = output
    
    return results


def check_package(package_name: str, import_name: str = None) -> Tuple[bool, str]:
    """
    Check if a Python package is installed.
    
    Args:
        package_name: Name of package (for pip display)
        import_name: Name to import (if different from package_name)
        
    Returns:
        (installed: bool, version: str)
    """
    if import_name is None:
        import_name = package_name.replace('-', '_')
    
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        return True, version
    except ImportError:
        return False, ""


def check_dependencies() -> Dict[str, Tuple[bool, str]]:
    """Check all required Python packages."""
    packages = {
        'psutil': 'psutil',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'onnxruntime': 'onnxruntime',
        'redis': 'redis',
        'flask': 'flask',
        'requests': 'requests',
        'coremltools': 'coremltools',
    }
    
    results = {}
    for package, import_name in packages.items():
        installed, version = check_package(package, import_name)
        results[package] = (installed, version)
    
    return results


def check_device_info() -> Dict[str, Any]:
    """Check device information detection."""
    try:
        sys.path.insert(0, str(Path.cwd()))
        from worker.legacy.device_info import get_device_info, get_compute_units
        
        device_info = get_device_info()
        compute_units = get_compute_units()
        
        return {
            'device_name': device_info.get('DeviceName'),
            'os': device_info.get('DeviceOs'),
            'os_version': device_info.get('DeviceOsVersion'),
            'soc': device_info.get('Soc'),
            'ram_gb': device_info.get('Ram'),
            'discrete_gpu': device_info.get('DiscreteGpu'),
            'compute_units': compute_units,
        }
    except Exception as e:
        return {'error': str(e)}


def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity."""
    results = {}
    
    # Check if redis-cli is available
    success, output = run_command(['redis-cli', '--version'])
    results['cli_available'] = success
    if success:
        results['cli_version'] = output
    
    # Try to connect to Redis
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        r.ping()
        results['connected'] = True
        results['info'] = "Redis is running"
    except Exception as e:
        results['connected'] = False
        results['error'] = str(e)
    
    return results


def check_orchestrator_connectivity(url: str = "http://localhost:5000") -> Dict[str, Any]:
    """Check orchestrator connectivity."""
    results = {'url': url}
    
    try:
        import requests
        response = requests.get(f"{url}/api/health", timeout=2)
        results['reachable'] = True
        results['status_code'] = response.status_code
        try:
            results['response'] = response.json()
        except:
            results['response'] = response.text
    except Exception as e:
        results['reachable'] = False
        results['error'] = str(e)
    
    return results


def check_network() -> Dict[str, Any]:
    """Check network connectivity."""
    results = {}
    
    # Get hostname and IP
    try:
        hostname = socket.gethostname()
        results['hostname'] = hostname
        results['ip_address'] = socket.gethostbyname(hostname)
    except Exception as e:
        results['network_error'] = str(e)
    
    # Check internet connectivity
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        results['internet'] = True
    except:
        results['internet'] = False
    
    return results


def check_model_formats() -> Dict[str, Any]:
    """Check model format support."""
    results = {}
    
    # ONNX
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        results['onnx'] = {
            'available': True,
            'version': ort.__version__,
            'providers': providers
        }
    except ImportError:
        results['onnx'] = {'available': False, 'error': 'Not installed'}
    except Exception as e:
        results['onnx'] = {'available': False, 'error': str(e)}
    
    # CoreML
    system = platform.system()
    if system == "Darwin":
        try:
            import coremltools
            results['coreml'] = {
                'available': True,
                'version': coremltools.__version__,
                'platform': 'macOS'
            }
        except ImportError:
            results['coreml'] = {'available': False, 'error': 'Not installed'}
        except Exception as e:
            results['coreml'] = {'available': False, 'error': str(e)}
    else:
        results['coreml'] = {'available': False, 'reason': f'CoreML not supported on {system}'}
    
    # PyTorch
    try:
        import torch
        results['pytorch'] = {
            'available': True,
            'version': torch.__version__,
            'cuda': torch.cuda.is_available()
        }
    except ImportError:
        results['pytorch'] = {'available': False, 'error': 'Not installed'}
    except Exception as e:
        results['pytorch'] = {'available': False, 'error': str(e)}
    
    # TensorFlow
    try:
        import tensorflow as tf
        results['tensorflow'] = {
            'available': True,
            'version': tf.__version__,
            'gpus': len(tf.config.list_physical_devices('GPU'))
        }
    except ImportError:
        results['tensorflow'] = {'available': False, 'error': 'Not installed'}
    except Exception as e:
        results['tensorflow'] = {'available': False, 'error': str(e)}
    
    return results


def validate_worker_setup() -> bool:
    """Validate worker node setup."""
    print_header("WORKER SETUP VALIDATION")
    all_passed = True
    
    # 1. Python Environment
    print_section("1. Python Environment")
    py_info = check_python()
    py_ok = py_info['version_ok']
    print_check("Python version >= 3.8", py_ok, py_info['version'])
    all_passed = all_passed and py_ok
    
    # 2. Platform Detection
    print_section("2. Platform Information")
    plat = check_platform()
    print_check("Platform detected", True, f"{plat['system']} {plat['release']}")
    
    # 3. Dependencies
    print_section("3. Core Dependencies")
    deps = check_dependencies()
    core_packages = ['psutil', 'numpy', 'pandas', 'onnxruntime', 'redis', 'flask', 'requests']
    
    for package in core_packages:
        installed, version = deps.get(package, (False, ""))
        print_check(f"  {package:25}", installed, version)
        all_passed = all_passed and installed
    
    # 4. Optional Dependencies
    print_section("4. Optional Dependencies")
    optional = {'coremltools': 'coremltools'}
    for package, import_name in optional.items():
        installed, version = deps.get(package, (False, ""))
        if plat['system'] == "Darwin":
            print_check(f"  {package:25}", installed, version if installed else "(optional on macOS)")
        else:
            print_check(f"  {package:25}", False, f"(not available on {plat['system']})")
    
    # 5. Device Information
    print_section("5. Device Detection")
    device_info = check_device_info()
    if 'error' not in device_info:
        print_check("Device info detected", True)
        print(f"    Device: {device_info.get('device_name', 'N/A')}")
        print(f"    OS: {device_info.get('os', 'N/A')} {device_info.get('os_version', 'N/A')}")
        print(f"    CPU: {device_info.get('soc', 'N/A')}")
        print(f"    RAM: {device_info.get('ram_gb', 'N/A')} GB")
        print(f"    Compute Units: {', '.join(device_info.get('compute_units', []))}")
    else:
        print_check("Device info detected", False, device_info['error'])
        all_passed = False
    
    # 6. Network
    print_section("6. Network Configuration")
    network = check_network()
    if 'network_error' not in network:
        print_check("Hostname detected", True, network.get('hostname'))
        print_check("Local IP detected", True, network.get('ip_address'))
    else:
        print_check("Network detection", False, network['network_error'])
    print_check("Internet connectivity", network.get('internet', False))
    
    # 7. Redis Connectivity
    print_section("7. Redis Connectivity")
    redis_info = check_redis()
    print_check("Redis CLI available", redis_info.get('cli_available', False))
    redis_connected = redis_info.get('connected', False)
    print_check("Redis server reachable", redis_connected, 
                redis_info.get('info', redis_info.get('error', '')))
    
    # 8. Orchestrator Connectivity
    print_section("8. Orchestrator Connectivity")
    orch = check_orchestrator_connectivity()
    orch_ok = orch.get('reachable', False)
    print_check("Orchestrator reachable", orch_ok, 
                orch.get('error', f"Status: {orch.get('status_code')}"))
    
    # 9. Model Format Support
    print_section("9. Model Format Support")
    models = check_model_formats()
    
    onnx_ok = models.get('onnx', {}).get('available', False)
    print_check("ONNX Runtime", onnx_ok, models.get('onnx', {}).get('version', ''))
    
    coreml_ok = models.get('coreml', {}).get('available', False)
    if plat['system'] == "Darwin":
        print_check("CoreML", coreml_ok, models.get('coreml', {}).get('version', ''))
    else:
        print_check("CoreML", False, f"(not available on {plat['system']})")
    
    pytorch_ok = models.get('pytorch', {}).get('available', False)
    print_check("PyTorch (optional)", pytorch_ok, models.get('pytorch', {}).get('version', ''))
    
    tf_ok = models.get('tensorflow', {}).get('available', False)
    print_check("TensorFlow (optional)", tf_ok, models.get('tensorflow', {}).get('version', ''))
    
    # Final summary
    print_section("Summary")
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ Worker setup is valid and ready!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Some checks failed. Review above.{Colors.RESET}")
    
    return all_passed


def validate_orchestrator_setup() -> bool:
    """Validate orchestrator setup."""
    print_header("ORCHESTRATOR SETUP VALIDATION")
    all_passed = True
    
    # 1. Python Environment
    print_section("1. Python Environment")
    py_info = check_python()
    py_ok = py_info['version_ok']
    print_check("Python version >= 3.8", py_ok, py_info['version'])
    all_passed = all_passed and py_ok
    
    # 2. Platform Detection
    print_section("2. Platform Information")
    plat = check_platform()
    print_check("Platform detected", True, f"{plat['system']} {plat['release']}")
    
    # 3. Dependencies
    print_section("3. Core Dependencies")
    deps = check_dependencies()
    core_packages = ['psutil', 'numpy', 'pandas', 'onnxruntime', 'redis', 'flask', 'requests']
    
    for package in core_packages:
        installed, version = deps.get(package, (False, ""))
        print_check(f"  {package:25}", installed, version)
        all_passed = all_passed and installed
    
    # 4. Database File
    print_section("4. Database File")
    db_file = Path('orchestrator_state.json')
    db_exists = db_file.exists()
    print_check("Database file exists", db_exists, str(db_file.absolute()))
    
    if not db_exists:
        try:
            # Try to create it
            from core.inmemory_store import InMemoryStore
            store = InMemoryStore(persistence_file=str(db_file))
            print_check("Database file created", True, "Auto-created")
        except Exception as e:
            print_check("Database file creation", False, str(e))
            all_passed = False
    
    # 5. Redis
    print_section("5. Redis Service")
    redis_info = check_redis()
    redis_ok = redis_info.get('connected', False)
    print_check("Redis server reachable", redis_ok, redis_info.get('info', redis_info.get('error', '')))
    
    if not redis_ok:
        print(f"    {Colors.YELLOW}Note: Redis can be started with: redis-server --port 6379{Colors.RESET}")
    
    # 6. Network
    print_section("6. Network Configuration")
    network = check_network()
    if 'network_error' not in network:
        print_check("Hostname detected", True, network.get('hostname'))
        print_check("Local IP detected", True, network.get('ip_address'))
    print_check("Internet connectivity", network.get('internet', False))
    
    # Final summary
    print_section("Summary")
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ Orchestrator setup is valid and ready!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Some checks failed. Review above.{Colors.RESET}")
    
    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='CycleOPS Setup Validation & Diagnostics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 setup_validation.py --mode worker
  python3 setup_validation.py --mode orchestrator
  python3 setup_validation.py --mode full-check
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['worker', 'orchestrator', 'full-check'],
        default='worker',
        help='Validation mode (default: worker)'
    )
    
    parser.add_argument(
        '--orchestrator-url',
        default='http://localhost:5000',
        help='Orchestrator URL (default: http://localhost:5000)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'worker':
        success = validate_worker_setup()
    elif args.mode == 'orchestrator':
        success = validate_orchestrator_setup()
    elif args.mode == 'full-check':
        print_header("FULL SYSTEM CHECK")
        w_success = validate_worker_setup()
        o_success = validate_orchestrator_setup()
        success = w_success and o_success
    else:
        success = False
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

