#!/usr/bin/env python3
"""
Listing Hub MCP Server Executable Wrapper.
Usage:
    ./scripts/listing_hub_mcp.py
Can be referenced in Claude Desktop config or Cursor MCP settings:
    {
      "mcpServers": {
        "listing-hub": {
          "command": "/Users/ondre/Projects/listing-hub/.venv/bin/python3.14",
          "args": ["/Users/ondre/Projects/listing-hub/scripts/listing_hub_mcp.py"]
        }
      }
    }
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from listing_hub.agent.mcp_server import main

if __name__ == "__main__":
    main()
