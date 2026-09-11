#!/usr/bin/env python3
"""
Listing Hub CLI Executable Wrapper.
Usage:
    ./scripts/listing_hub_cli.py summary
    ./scripts/listing_hub_cli.py list --status active
    ./scripts/listing_hub_cli.py radar "Makita vrtacka"
"""

import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from listing_hub.agent.cli import main

if __name__ == "__main__":
    sys.exit(main())
