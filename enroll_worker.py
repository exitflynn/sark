#!/usr/bin/env python3
"""
CycleOPS Worker Enrollment Script

Automated setup and registration of a worker node with the orchestrator.
Handles platform-specific configuration and dependency installation.

Usage:
    python3 enroll_worker.py --orchestrator-url http://192.168.1.100:5000
"""

import sys
import os
import json
import platform
import argparse
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import socket
import uuid


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class WorkerEnroller:
    """Handles worker enrollment process."""
    
    def __init__(self, orchestrator_url: str, redis_host: str, redis_port: int, 
                 config_file: str = 'worker_config.json'):
        """
        Initialize worker enroller.
        
        Args:
            orchestrator_url: Orchestrator URL
            redis_host: Redis host
            redis_port: Redis port
            config_file: Configuration file name
        """
        self.orchestrator_url = orchestrator_url
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.config_file = config_file
        self.platform_info = self._get_platform_info()
        self.device_info = {}
        self.capabilities = []
    
    def print_header(self, text: str):
        """Print formatted header."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")
    
    def print_section(self, text: str):
        """Print formatted section."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
        print(f"{'-'*70}")
    
    def print_check(self, name: str, passed: bool, message: str = ""):
        """Print check result."""
        status = f"{Colors.GREEN}✅{Colors.RESET}" if passed else f"{Colors.RED}❌{Colors.RESET}"
        detail = f" {message}" if message else ""
        print(f"  {status} {name}{detail}")
    
    def print_info(self, text: str):
        """Print informational message."""
        print(f"  {Colors.BLUE}ℹ️ {text}{Colors.RESET}")
    
    def print_warning(self, text: str):
        """Print warning message."""
        print(f"  {Colors.YELLOW}⚠️  {text}{Colors.RESET}")
    
    def print_success(self, text: str):
        """Print success message."""
        print(f"  {Colors.GREEN}✅ {text}{Colors.RESET}")
    
    def print_error(self, text: str):
        """Print error message."""
        print(f"  {Colors.RED}❌ {text}{Colors.RESET}")
    
    def _get_platform_info(self) -> Dict[str, str]:
        """Get platform information."""
        system = platform.system()
        return {
            'system': system,
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'is_macos': system == "Darwin",
            'is_windows': system == "Windows",
            'is_linux': system == "Linux",
        }
    
    def run_command(self, cmd: str, shell: bool = True) -> Tuple[bool, str]:
        """
        Run a command.
        
        Args:
            cmd: Command to run
            shell: If True, run as shell command
            
        Returns:
            (success: bool, output: str)
        """
        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def step_1_validate_environment(self) -> bool:
        """Step 1: Validate Python environment."""
        self.print_section("Step 1: Validating Python Environment")
        
        version_info = sys.version_info
        if version_info < (3, 8):
            self.print_error(f"Python 3.8+ required, got {version_info.major}.{version_info.minor}")
            return False
        
        self.print_check("Python version", True, f"{version_info.major}.{version_info.minor}.{version_info.micro}")
        
        # Check virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        
        if not in_venv:
            self.print_warning("Not running in virtual environment")
            self.print_info("Recommendation: Create one with 'python3 -m venv .env_worker'")
        else:
            self.print_check("Virtual environment", True, sys.prefix)
        
        return True
    
    def step_2_detect_platform(self) -> bool:
        """Step 2: Detect platform and capabilities."""
        self.print_section("Step 2: Detecting Platform & Capabilities")
        
        system = self.platform_info['system']
        self.print_check("Platform detected", True, f"{system} {self.platform_info['release']}")
        
        # Get device info
        try:
            sys.path.insert(0, str(Path.cwd()))
            from worker.legacy.device_info import get_device_info, get_compute_units
            
            self.device_info = get_device_info()
            self.capabilities = get_compute_units()
            
            self.print_check("Device name", True, self.device_info.get('DeviceName', 'N/A'))
            self.print_check("CPU/SOC", True, self.device_info.get('Soc', 'N/A')[:50])
            self.print_check("RAM", True, f"{self.device_info.get('Ram', 0)} GB")
            
            # Platform-specific capabilities
            if system == "Darwin":
                self.print_check("OS", True, "macOS (CoreML supported)")
            elif system == "Windows":
                self.print_check("OS", True, "Windows (ONNX DML support)")
            else:
                self.print_check("OS", True, f"{system} (CPU inference)")
            
            self.print_check("Compute units", True, ", ".join(self.capabilities))
            
            return True
        except Exception as e:
            self.print_error(f"Failed to detect device info: {e}")
            return False
    
    def step_3_validate_dependencies(self) -> bool:
        """Step 3: Validate Python dependencies."""
        self.print_section("Step 3: Validating Python Dependencies")
        
        # Check for pip
        success, _ = self.run_command("pip --version")
        if not success:
            self.print_error("pip not found. Install Python dev tools.")
            return False
        
        self.print_check("pip", True)
        
        # List of required packages
        required = {
            'psutil': 'psutil',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'onnxruntime': 'onnxruntime',
            'redis': 'redis',
            'flask': 'flask',
            'requests': 'requests',
        }
        
        # Platform-specific optional
        optional = {}
        if self.platform_info['is_macos']:
            optional['coremltools'] = 'coremltools'
        
        missing = []
        
        # Check required
        for display_name, import_name in required.items():
            try:
                module = __import__(import_name)
                version = getattr(module, '__version__', 'unknown')
                self.print_check(f"  {display_name:25}", True, version)
            except ImportError:
                self.print_check(f"  {display_name:25}", False)
                missing.append(import_name)
        
        # Check optional
        for display_name, import_name in optional.items():
            try:
                module = __import__(import_name)
                version = getattr(module, '__version__', 'unknown')
                self.print_check(f"  {display_name:25} (optional)", True, version)
            except ImportError:
                self.print_check(f"  {display_name:25} (optional)", False)
        
        if missing:
            self.print_error(f"Missing dependencies: {', '.join(missing)}")
            self.print_info(f"Install with: pip install {' '.join(missing)}")
            return False
        
        return True
    
    def step_4_test_connectivity(self) -> bool:
        """Step 4: Test network connectivity."""
        self.print_section("Step 4: Testing Network Connectivity")
        
        # Get hostname and IP
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            self.print_check("Hostname", True, hostname)
            self.print_check("Local IP", True, ip_address)
        except Exception as e:
            self.print_error(f"Failed to detect hostname/IP: {e}")
            return False
        
        # Test orchestrator connectivity
        self.print_info(f"Testing orchestrator at {self.orchestrator_url}")
        try:
            import requests
            response = requests.get(
                f"{self.orchestrator_url}/api/health",
                timeout=5
            )
            if response.status_code == 200:
                self.print_check("Orchestrator reachable", True)
            else:
                self.print_error(f"Orchestrator returned {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            self.print_error(f"Cannot connect to orchestrator at {self.orchestrator_url}")
            self.print_info("Ensure orchestrator is running and reachable")
            return False
        except Exception as e:
            self.print_error(f"Orchestrator connectivity error: {e}")
            return False
        
        # Test Redis connectivity
        self.print_info(f"Testing Redis at {self.redis_host}:{self.redis_port}")
        try:
            import redis
            r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                socket_connect_timeout=2
            )
            r.ping()
            self.print_check("Redis reachable", True)
        except Exception as e:
            self.print_warning(f"Redis not reachable: {e}")
            self.print_info("Worker can still function, but with limited capabilities")
        
        return True
    
    def step_5_register_worker(self) -> bool:
        """Step 5: Register worker with orchestrator."""
        self.print_section("Step 5: Registering Worker with Orchestrator")
        
        try:
            import requests
            
            registration_data = {
                'device_name': self.device_info.get('DeviceName', 'Unknown'),
                'ip_address': socket.gethostbyname(socket.gethostname()),
                'capabilities': self.capabilities,
                'device_info': {
                    'DeviceName': self.device_info.get('DeviceName', ''),
                    'Soc': self.device_info.get('Soc', ''),
                    'Ram': self.device_info.get('Ram', 0),
                    'DeviceOs': self.device_info.get('DeviceOs', ''),
                    'DeviceOsVersion': self.device_info.get('DeviceOsVersion', ''),
                }
            }
            
            self.print_info(f"Registering {registration_data['device_name']}")
            
            response = requests.post(
                f"{self.orchestrator_url}/api/register",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                worker_id = result.get('worker_id')
                self.print_success(f"Worker registered as {worker_id}")
                
                # Save registration info
                registration_info = {
                    'worker_id': worker_id,
                    'registered_at': time.time(),
                    'device_info': registration_data,
                    'orchestrator': self.orchestrator_url,
                }
                
                reg_file = Path('.worker_registration.json')
                with open(reg_file, 'w') as f:
                    json.dump(registration_info, f, indent=2)
                
                self.print_info(f"Registration saved to {reg_file}")
                return True
            else:
                self.print_error(f"Registration failed: {response.status_code}")
                self.print_info(f"Response: {response.text}")
                return False
        
        except Exception as e:
            self.print_error(f"Registration error: {e}")
            return False
    
    def step_6_create_config(self) -> bool:
        """Step 6: Create worker configuration file."""
        self.print_section("Step 6: Creating Worker Configuration")
        
        try:
            config = {
                'orchestrator': {
                    'url': self.orchestrator_url,
                    'timeout': 10,
                    'retry_attempts': 3
                },
                'redis': {
                    'host': self.redis_host,
                    'port': self.redis_port,
                    'timeout': 5
                },
                'worker': {
                    'heartbeat_interval': 10,
                    'job_timeout': 3600,
                    'model_cache_dir': './model_cache'
                },
                'logging': {
                    'level': 'INFO',
                    'file': 'worker.log'
                }
            }
            
            config_path = Path(self.config_file)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.print_success(f"Configuration saved to {config_path}")
            
            # Create model cache directory
            cache_dir = Path(config['worker']['model_cache_dir'])
            cache_dir.mkdir(exist_ok=True)
            self.print_check("Model cache directory", True, str(cache_dir.absolute()))
            
            return True
        
        except Exception as e:
            self.print_error(f"Configuration creation error: {e}")
            return False
    
    def step_7_verify_registration(self) -> bool:
        """Step 7: Verify worker registration."""
        self.print_section("Step 7: Verifying Worker Registration")
        
        try:
            import requests
            
            response = requests.get(
                f"{self.orchestrator_url}/api/workers",
                timeout=5
            )
            
            if response.status_code == 200:
                workers = response.json()
                
                # Find this worker
                device_name = self.device_info.get('DeviceName', 'Unknown')
                found = False
                
                for worker_id, worker in workers.items():
                    if worker.get('device_name') == device_name:
                        self.print_success(f"Worker found in registry")
                        self.print_check("Worker ID", True, worker_id)
                        self.print_check("Status", True, worker.get('status', 'UNKNOWN'))
                        self.print_check("Capabilities", True, 
                                        ", ".join(worker.get('capabilities', [])))
                        found = True
                        break
                
                if not found:
                    self.print_warning("Worker not found in registry yet")
                    self.print_info("This is normal - try again in a few seconds")
                
                return True
            else:
                self.print_error(f"Failed to query workers: {response.status_code}")
                return False
        
        except Exception as e:
            self.print_error(f"Verification error: {e}")
            return False
    
    def run_enrollment(self) -> bool:
        """Run complete enrollment process."""
        self.print_header("CycleOPS WORKER ENROLLMENT")
        
        print(f"{Colors.CYAN}This script will register this device as a worker with the CycleOPS orchestrator.{Colors.RESET}\n")
        
        steps = [
            ("Environment", self.step_1_validate_environment),
            ("Platform Detection", self.step_2_detect_platform),
            ("Dependency Check", self.step_3_validate_dependencies),
            ("Connectivity Test", self.step_4_test_connectivity),
            ("Worker Registration", self.step_5_register_worker),
            ("Configuration", self.step_6_create_config),
            ("Verification", self.step_7_verify_registration),
        ]
        
        failed_steps = []
        
        for step_name, step_func in steps:
            try:
                success = step_func()
                if not success:
                    failed_steps.append(step_name)
                    self.print_warning(f"⚠️  {step_name} - Some checks failed")
            except Exception as e:
                failed_steps.append(step_name)
                self.print_error(f"❌ {step_name} - Unexpected error: {e}")
        
        # Print summary
        self.print_section("ENROLLMENT SUMMARY")
        
        if not failed_steps:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ ENROLLMENT SUCCESSFUL!{Colors.RESET}\n")
            print(f"Worker is ready to accept jobs.")
            print(f"\nTo start the worker agent, run:")
            print(f"  {Colors.CYAN}python3 worker/worker_agent.py \\")
            print(f"    --orchestrator-url {self.orchestrator_url} \\")
            print(f"    --redis-host {self.redis_host} \\")
            print(f"    --redis-port {self.redis_port}{Colors.RESET}\n")
            return True
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  ENROLLMENT INCOMPLETE{Colors.RESET}\n")
            print(f"Failed steps: {', '.join(failed_steps)}\n")
            print(f"Review errors above and try again.\n")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='CycleOPS Worker Enrollment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 enroll_worker.py --orchestrator-url http://localhost:5000
  python3 enroll_worker.py --orchestrator-url http://192.168.1.100:5000 \\
                          --redis-host 192.168.1.100 --redis-port 6379
        """
    )
    
    parser.add_argument(
        '--orchestrator-url',
        required=True,
        help='Orchestrator URL (required)'
    )
    
    parser.add_argument(
        '--redis-host',
        default='localhost',
        help='Redis host (default: localhost)'
    )
    
    parser.add_argument(
        '--redis-port',
        type=int,
        default=6379,
        help='Redis port (default: 6379)'
    )
    
    parser.add_argument(
        '--config-file',
        default='worker_config.json',
        help='Configuration file name (default: worker_config.json)'
    )
    
    args = parser.parse_args()
    
    # Run enrollment
    enroller = WorkerEnroller(
        orchestrator_url=args.orchestrator_url,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        config_file=args.config_file
    )
    
    success = enroller.run_enrollment()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

