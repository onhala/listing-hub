import pytest
import json
from unittest.mock import patch, MagicMock
from app import app as flask_app
import listing_hub.core.db as db

@pytest.fixture
def client():
    flask_app.testing = True
    with flask_app.test_client() as client:
        yield client

def test_agent_summary_endpoint(client):
    res = client.get("/api/agent/v1/summary")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "ok"
    assert "summary" in data
    s = data["summary"]
    assert "total_listings" in s
    assert "active_count" in s
    assert "draft_count" in s
    assert "sold_count" in s
    assert "worker" in s
    assert s["worker"]["running"] is False
    from listing_hub.core.version import APP_VERSION
    assert s["app_version"] == APP_VERSION

def test_agent_listings_query(client):
    res = client.get("/api/agent/v1/listings?status=all&limit=10")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "ok"
    assert "count" in data
    assert "listings" in data
    assert isinstance(data["listings"], list)

def test_agent_create_draft_success(client):
    with patch("listing_hub.core.db.save_listing") as mock_save:
        payload = {
            "title": "Aku šroubovák Bosch Professional 18V",
            "price": 1850,
            "description": "STAV: Velmi dobrý, plně funkční.\nPŘÍSLUŠENSTVÍ: 1x akumulátor 2.0Ah, nabíječka.",
            "category": "Nářadí",
            "condition": "Použité"
        }
        res = client.post("/api/agent/v1/draft", json=payload)
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["status"] == "success"
        assert data["listing"]["title"] == "Aku šroubovák Bosch Professional 18V"
        assert data["listing"]["price"] == 1850
        assert mock_save.called

def test_agent_create_draft_missing_title(client):
    res = client.post("/api/agent/v1/draft", json={"price": 1000})
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Missing required field 'title'" in data["message"]

def test_agent_create_draft_path_traversal_blocked(client):
    payload = {
        "title": "Bezpečnostní test",
        "price": 500,
        "local_photos_dir": "../../etc/passwd"
    }
    res = client.post("/api/agent/v1/draft", json=payload)
    assert res.status_code == 400
    data = json.loads(res.data)
    assert data["error_code"] == "INVALID_PHOTOS_DIR"

def test_agent_action_status(client):
    res = client.get("/api/agent/v1/actions/status")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "ok"
    assert "state" in data
    assert "running" in data
    assert "screencast_url" in data

def test_agent_action_cancel(client):
    with patch("app.session_manager.cancel_current_action"):
        res = client.post("/api/agent/v1/actions/cancel")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "success"

def test_agent_market_radar(client):
    mock_radar_return = {
        "title": "Makita DHP484",
        "current_price": 0,
        "status": "FAIR",
        "message": "Tržní analýza dokončena",
        "diff_percent": 0,
        "stats": {
            "min": 1800,
            "max": 2800,
            "median": 2200,
            "suggested_fair": 2200,
            "suggested_quick_sale": 1980,
            "suggested_premium": 2420
        },
        "reasoning": "Na základě 12 inzerátů na Bazoši a Sbazaru.",
        "sources_checked": ["Bazoš.cz", "Sbazar.cz"],
        "listings": []
    }
    with patch("listing_hub.agent.api.unified_market_price_radar", return_value=mock_radar_return):
        res = client.post("/api/agent/v1/radar", json={"query": "Makita DHP484"})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "ok"
        assert data["radar"]["stats"]["median"] == 2200

def test_agent_auth_bearer_token_enforcement(client):
    # Test that when LISTING_HUB_API_TOKEN is set, unauthorized requests are rejected
    with patch.dict("os.environ", {"LISTING_HUB_API_TOKEN": "secret-agent-token-123"}):
        # 1. No auth header -> 401
        res_no_auth = client.get("/api/agent/v1/summary")
        assert res_no_auth.status_code == 401
        data = json.loads(res_no_auth.data)
        assert data["error_code"] == "AUTH_FAILED"

        # 2. Invalid auth header -> 401
        res_bad_auth = client.get(
            "/api/agent/v1/summary",
            headers={"Authorization": "Bearer wrong-token"}
        )
        assert res_bad_auth.status_code == 401

        # 3. Valid auth header -> 200
        res_good_auth = client.get(
            "/api/agent/v1/summary",
            headers={"Authorization": "Bearer secret-agent-token-123"}
        )
        assert res_good_auth.status_code == 200


def test_agent_debug_dom(client):
    mock_dom = {
        "active": True,
        "url": "https://dum.bazos.cz/pridat-inzerat.php",
        "title": "Bazoš.cz - Přidat inzerát",
        "errors": ["Chybné heslo"],
        "warnings": [],
        "has_sms_input": True,
        "inputs": [{"tag": "input", "name": "klic", "value": ""}],
        "buttons": ["Odeslat"],
        "body_snippet": "Bazoš přidání inzerátu..."
    }
    with patch("post_to_bazos.session_manager.inspect_dom", return_value=mock_dom):
        res = client.get("/api/agent/v1/debug/dom")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "ok"
        assert data["dom"]["active"] is True
        assert data["dom"]["has_sms_input"] is True
        assert "Chybné heslo" in data["dom"]["errors"]


def test_agent_debug_logs(client, tmp_path):
    mock_log_file = tmp_path / "test_app.log"
    mock_log_file.write_text(
        "2026-09-11 15:00:00 [INFO] app: Server started\n"
        "2026-09-11 15:01:00 [ERROR] worker: Connection timeout\n",
        encoding="utf-8"
    )
    with patch("listing_hub.core.config.LOG_FILE_PATH", mock_log_file):
        # 1. Fetch all lines
        res = client.get("/api/agent/v1/debug/logs?lines=10")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "ok"
        assert len(data["logs"]) == 2
        assert "Server started" in data["logs"][0]

        # 2. Filter by level
        res_filtered = client.get("/api/agent/v1/debug/logs?level=ERROR")
        assert res_filtered.status_code == 200
        data_filtered = json.loads(res_filtered.data)
        assert len(data_filtered["logs"]) == 1
        assert "Connection timeout" in data_filtered["logs"][0]

