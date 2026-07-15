import os
import sys
import json
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

@pytest.fixture(autouse=True)
def mock_db():
    db_uri = "file::memory:?cache=shared"
    # Keep one connection open to prevent in-memory DB deletion
    keep_alive = sqlite3.connect(db_uri, uri=True)
    
    def get_mock_conn():
        conn = sqlite3.connect(db_uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    with patch("listing_hub.core.db.get_db_connection", side_effect=get_mock_conn):
        from listing_hub.core.db import init_db
        init_db()
        yield
        keep_alive.close()

@pytest.fixture(autouse=True)
def mock_config(tmp_path, monkeypatch):
    temp_config_path = tmp_path / "bazos_config.json"
    temp_session_path = tmp_path / "bazos_session.json"
    temp_listings_path = tmp_path / "bazos_active_listings.json"
    
    mock_config_data = {
        "jmeno": "Test User",
        "email": "test@example.com",
        "phone": "123456789",
        "psc": "12345",
        "default_ad_password_b64": "aGVzbG8xMjM=",
        "gemini_api_key": "dummy_api_key",
        "user": {
            "email": "test@example.com",
            "phone": "123456789",
            "phone_verified": "+420123456789",
            "default_ad_password_b64": "aGVzbG8xMjM=",
            "name": "Test User",
            "zip_code": "12345",
            "location": "Praha 12345",
            "gemini_api_key": "dummy_api_key"
        }
    }
    with open(temp_config_path, "w", encoding="utf-8") as f:
        json.dump(mock_config_data, f)
        
    with open(temp_listings_path, "w", encoding="utf-8") as f:
        json.dump({"active_listings": [], "sold_listings": []}, f)
        
    monkeypatch.setattr("listing_hub.core.config.CONFIG_PATH", temp_config_path)
    monkeypatch.setattr("listing_hub.core.config.SESSION_STATE_PATH", temp_session_path)
    
    monkeypatch.setattr("post_to_bazos.CONFIG_PATH", temp_config_path)
    monkeypatch.setattr("post_to_bazos.SESSION_STATE_PATH", temp_session_path)
    monkeypatch.setattr("post_to_bazos.LISTINGS_PATH", temp_listings_path)
    
    return mock_config_data

@pytest.fixture(autouse=True)
def mock_playwright_session():
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    
    mock_page.url = "https://example.com"
    mock_page.is_closed.return_value = False
    mock_browser.is_connected.return_value = True
    
    with patch("post_to_bazos.session_manager.get_session", return_value=(mock_playwright, mock_browser, mock_context, mock_page)), \
         patch("listing_hub.portals.bazos.session.session_manager.get_session", return_value=(mock_playwright, mock_browser, mock_context, mock_page)):
        yield (mock_playwright, mock_browser, mock_context, mock_page)
