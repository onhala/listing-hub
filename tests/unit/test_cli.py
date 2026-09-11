import pytest
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from listing_hub.agent.cli import build_parser, handle_summary, handle_list, handle_draft
from listing_hub.agent.mcp_server import McpServer, TOOLS_SCHEMA

def test_cli_parser_subcommands():
    parser = build_parser()
    
    # Test summary parsing
    args = parser.parse_args(["summary", "--json"])
    assert args.subcommand == "summary"
    assert args.json is True

    # Test list parsing
    args = parser.parse_args(["list", "--status", "active", "--limit", "25"])
    assert args.subcommand == "list"
    assert args.status == "active"
    assert args.limit == 25

    # Test draft parsing
    args = parser.parse_args(["draft", "Sekačka Gardena", "--price", "3500", "--radar"])
    assert args.subcommand == "draft"
    assert args.title == "Sekačka Gardena"
    assert args.price == 3500
    assert args.radar is True

    # Test repost parsing
    args = parser.parse_args(["repost", "item_123", "2990"])
    assert args.subcommand == "repost"
    assert args.id == "item_123"
    assert args.new_price == 2990

def test_cli_summary_sqlite_fallback(capsys):
    parser = build_parser()
    args = parser.parse_args(["--server", "http://127.0.0.1:59999", "summary", "--json"])
    code = handle_summary(args)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["mode"] == "sqlite_fallback"
    assert "summary" in data

def test_cli_list_sqlite_fallback(capsys):
    parser = build_parser()
    args = parser.parse_args(["--server", "http://127.0.0.1:59999", "list", "--json", "--status", "all"])
    code = handle_list(args)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert "listings" in data

def test_mcp_server_tools_schema():
    assert len(TOOLS_SCHEMA) >= 10
    tool_names = [t["name"] for t in TOOLS_SCHEMA]
    assert "listing_hub_summary" in tool_names
    assert "listing_hub_list_listings" in tool_names
    assert "listing_hub_market_radar" in tool_names
    assert "listing_hub_create_draft" in tool_names
    assert "listing_hub_post_ad" in tool_names
    assert "listing_hub_confirm_submission" in tool_names

def test_mcp_server_execute_summary():
    server = McpServer(server_url="http://127.0.0.1:59999")
    result_str = server.execute_tool("listing_hub_summary", {})
    data = json.loads(result_str)
    assert data["status"] == "ok"
    assert "summary" in data

def test_mcp_server_execute_list():
    server = McpServer(server_url="http://127.0.0.1:59999")
    result_str = server.execute_tool("listing_hub_list_listings", {"status": "all"})
    data = json.loads(result_str)
    assert data["status"] == "ok"
    assert "listings" in data
