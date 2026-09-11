"""
Listing Hub MCP Server (Model Context Protocol).
Author: Ondřej Hála

A zero-dependency stdio JSON-RPC 2.0 implementation of the Model Context Protocol (MCP).
Allows any MCP-compatible AI client (Claude Desktop, Cursor, Antigravity) to manage
listings, run market radars, and orchestrate the two-phase posting workflow.
"""

import sys
import json
import os
from typing import Dict, Any, List, Optional
import requests

from listing_hub.core.version import APP_VERSION
from listing_hub.agent.cli import DEFAULT_SERVER, API_PREFIX, get_headers, local_db_summary, local_db_list


SERVER_NAME = "listing-hub"
SERVER_VERSION = APP_VERSION
PROTOCOL_VERSION = "2024-11-05"

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "listing_hub_summary",
        "description": "Get a token-efficient executive overview of all listings, counts (active, draft, sold, in review), expiring ads, and background worker status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_list_listings",
        "description": "List listings with optional status filter (active, draft, sold, needs_review, all), search query, and pagination limit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "active", "draft", "sold", "needs_review"],
                    "description": "Filter by listing lifecycle status (default: 'all')"
                },
                "search": {
                    "type": "string",
                    "description": "Optional search term to filter by title or description"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of listings to return (default: 50, max: 200)"
                }
            },
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_get_listing",
        "description": "Retrieve complete details, photo file list, description, and portal states for a specific listing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Listing ID or local photos directory"
                }
            },
            "required": ["id"],
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_market_radar",
        "description": "Query live multi-source market price radar (Bazoš.cz, Sbazar.cz, Web search, and AI fallback) to get price distributions and fair/quick-sale recommendations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query or product title (e.g. 'Makita DHP484')"
                },
                "brand": {
                    "type": "string",
                    "description": "Optional brand name"
                },
                "model": {
                    "type": "string",
                    "description": "Optional model number"
                },
                "condition": {
                    "type": "string",
                    "description": "Item condition (default: 'Použité')"
                },
                "fallback_price": {
                    "type": "integer",
                    "description": "Optional seller price estimate to anchor valuation"
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_create_draft",
        "description": "Create a new uncommitted draft listing with title (max 50 chars), price, description, and optional market radar valuation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Listing title, max 50 characters (e.g. 'Aku vrtačka Makita DHP484 bez aku')"
                },
                "price": {
                    "type": "integer",
                    "description": "Asking price in CZK (0 for negotiable/unspecified)"
                },
                "description": {
                    "type": "string",
                    "description": "Plaintext listing description without markdown asterisks"
                },
                "category": {
                    "type": "string",
                    "description": "Bazoš category/section"
                },
                "condition": {
                    "type": "string",
                    "description": "Item condition (e.g. 'Použité', 'Nové')"
                },
                "local_photos_dir": {
                    "type": "string",
                    "description": "Directory of photos relative to photos/ (e.g. 'photos/makita_123')"
                },
                "notes": {
                    "type": "string",
                    "description": "Private seller notes"
                },
                "auto_market_radar": {
                    "type": "boolean",
                    "description": "If true, queries market radar to suggest fair price automatically"
                }
            },
            "required": ["title"],
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_post_ad",
        "description": "Phase 1: Supervised ad posting initialization. Dispatches browser worker to prefill Bazos form and safely halts in 'ready_for_review'. Returns live screencast URL for user review.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "listing_id": {
                    "type": "string",
                    "description": "Listing ID to post"
                },
                "target_domain": {
                    "type": "string",
                    "description": "Target Bazoš subdomain (e.g. 'dum.bazos.cz', 'elektro.bazos.cz') to prevent redirect form resets"
                }
            },
            "required": ["listing_id"],
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_check_status",
        "description": "Check current browser worker state (idle, running, ready_for_review, completed, error) and retrieve live screencast link.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_confirm_submission",
        "description": "Phase 2: Finalize submission after user inspects and submits the form in the live browser view. Verifies live Bazos ad URL and activates listing.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_cancel_action",
        "description": "Immediately terminate active browser session and reset worker state without altering draft.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_repost_listing",
        "description": "Repost an existing or stale listing with a new price point (top-up ad) on Bazoš.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "listing_id": {
                    "type": "string",
                    "description": "Listing ID to repost"
                },
                "new_price": {
                    "type": "integer",
                    "description": "New price in CZK"
                },
                "target_domain": {
                    "type": "string",
                    "description": "Optional explicit target subdomain"
                }
            },
            "required": ["listing_id", "new_price"],
            "additionalProperties": False
        }
    },
    {
        "name": "listing_hub_delete_listing",
        "description": "Permanently purge a listing from local SQLite database and optionally delete local photos directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "listing_id": {
                    "type": "string",
                    "description": "Listing ID to delete"
                },
                "delete_photos": {
                    "type": "boolean",
                    "description": "If true, also permanently remove photos directory from disk"
                }
            },
            "required": ["listing_id"],
            "additionalProperties": False
        }
    }
]


class McpServer:
    def __init__(self, server_url: str = DEFAULT_SERVER, token: Optional[str] = None):
        self.server_url = server_url.rstrip('/')
        self.token = token or os.environ.get("LISTING_HUB_API_TOKEN")

    def _api_request(self, method: str, path: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
        url = f"{self.server_url}{API_PREFIX}{path}"
        headers = get_headers(self.token)
        try:
            resp = requests.request(method=method, url=url, headers=headers, json=json_data, params=params, timeout=timeout)
            return resp.json()
        except requests.exceptions.ConnectionError:
            # Fallback for read queries
            if method == "GET" and path == "/summary":
                return local_db_summary()
            if method == "GET" and path.startswith("/listings"):
                status_f = (params or {}).get("status", "all")
                search_q = (params or {}).get("search", "")
                limit_q = (params or {}).get("limit", 50)
                return local_db_list(status_filter=status_f, search=search_q, limit=limit_q)
            raise RuntimeError("Listing Hub server is not running at " + self.server_url)

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        try:
            if name == "listing_hub_summary":
                res = self._api_request("GET", "/summary")
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_list_listings":
                params = {
                    "status": arguments.get("status", "all"),
                    "search": arguments.get("search", ""),
                    "limit": arguments.get("limit", 50)
                }
                res = self._api_request("GET", "/listings", params=params)
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_get_listing":
                res = self._api_request("GET", f"/listings/{arguments['id']}")
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_market_radar":
                payload = {
                    "query": arguments["query"],
                    "brand": arguments.get("brand", ""),
                    "model": arguments.get("model", ""),
                    "condition": arguments.get("condition", "Použité"),
                    "fallback_price": arguments.get("fallback_price", 0)
                }
                res = self._api_request("POST", "/radar", json_data=payload, timeout=45.0)
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_create_draft":
                payload = {
                    "title": arguments["title"],
                    "price": arguments.get("price", 0),
                    "description": arguments.get("description", ""),
                    "category": arguments.get("category", ""),
                    "condition": arguments.get("condition", "Použité"),
                    "local_photos_dir": arguments.get("local_photos_dir", ""),
                    "notes": arguments.get("notes", ""),
                    "auto_market_radar": arguments.get("auto_market_radar", False)
                }
                res = self._api_request("POST", "/draft", json_data=payload)
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_post_ad":
                payload = {"listing_id": arguments["listing_id"]}
                if arguments.get("target_domain"):
                    payload["target_domain"] = arguments["target_domain"]
                res = self._api_request("POST", "/actions/post", json_data=payload)
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_check_status":
                res = self._api_request("GET", "/actions/status")
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_confirm_submission":
                res = self._api_request("POST", "/actions/confirm")
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_cancel_action":
                res = self._api_request("POST", "/actions/cancel")
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_repost_listing":
                payload = {
                    "listing_id": arguments["listing_id"],
                    "new_price": arguments["new_price"]
                }
                if arguments.get("target_domain"):
                    payload["target_domain"] = arguments["target_domain"]
                res = self._api_request("POST", "/actions/repost", json_data=payload)
                return json.dumps(res, indent=2, ensure_ascii=False)

            elif name == "listing_hub_delete_listing":
                payload = {"delete_photos": arguments.get("delete_photos", False)}
                res = self._api_request("DELETE", f"/listings/{arguments['listing_id']}", json_data=payload)
                return json.dumps(res, indent=2, ensure_ascii=False)

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def run_stdio(self):
        """Run standard I/O JSON-RPC processing loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request_obj = json.loads(line)
            except Exception as parse_err:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {parse_err}"}
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
                continue

            req_id = request_obj.get("id")
            method = request_obj.get("method")
            params = request_obj.get("params", {})

            # 1. Initialize
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {"listChanged": False}
                        },
                        "serverInfo": {
                            "name": SERVER_NAME,
                            "version": SERVER_VERSION
                        }
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            # 2. Initialized notification
            elif method == "notifications/initialized":
                pass

            # 3. Ping
            elif method == "ping":
                response = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            # 4. Tools List
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": TOOLS_SCHEMA
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            # 5. Tools Call
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                tool_result_str = self.execute_tool(tool_name, tool_args)

                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": tool_result_str
                            }
                        ]
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            else:
                if req_id is not None:
                    error_resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }
                    sys.stdout.write(json.dumps(error_resp) + "\n")
                    sys.stdout.flush()


def main():
    server = McpServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
