"""
Falcon AI Desktop Assistant - Root Launcher.
Developed by: HarshGuruJi
"""

import sys
from pathlib import Path

# Ensure package is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from falcon.main import main

if __name__ == "__main__":
    main()
