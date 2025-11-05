#!/usr/bin/env python3
"""
Wrapper script to properly run the worker agent from any directory.
This ensures Python path is set up correctly for imports.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now import and run the worker
from worker.worker_agent import main

if __name__ == '__main__':
    sys.exit(main())

