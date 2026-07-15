import pytest
import json
from unittest.mock import patch, MagicMock
from app import app as flask_app, count_photos

@pytest.fixture
def client():
    flask_app.testing = True
    with flask_app.test_client() as client:
        yield client

@patch("os.path.isdir")
@patch("os.listdir")
def test_count_photos(mock_listdir, mock_isdir):
    mock_isdir.return_value = True
    mock_listdir.return_value = ["foto_1.jpg", "foto_2.png", "document.pdf", "readme.txt"]
    
    # Bez vyloučení fotek
    total, included = count_photos("dummy_dir", [])
    assert total == 2
    assert included == 2
    
    # S vyloučením jedné fotky
    total, included = count_photos("dummy_dir", ["foto_1.jpg"])
    assert total == 2
    assert included == 1

@patch("app.IS_DOCKER", True)
def test_version_update_blocked_in_docker(client):
    res = client.post("/api/version/update")
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "V Dockeru nelze spustit" in data["message"]

@patch("app.IS_DOCKER", False)
@patch("subprocess.check_output")
@patch("os._exit")
def test_version_update_success_local(mock_exit, mock_subprocess, client):
    mock_subprocess.return_value = b"Already up to date."
    res = client.post("/api/version/update")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert "Already up to date." in data["message"]

def test_safe_merge_logic_simulation():
    fresh_data = {
        "active_listings": [
            {"local_photos_dir": "photos/item1", "title": "Stůl", "views": 10, "status": "Aktivní"}
        ],
        "sold_listings": []
    }
    local_data = {
        "active_listings": [
            {"local_photos_dir": "photos/item1", "title": "Stůl", "views": 25, "status": "Aktivní"}
        ],
        "sold_listings": []
    }
    
    fresh_active = {ad["local_photos_dir"]: ad for ad in fresh_data["active_listings"]}
    for local_ad in local_data["active_listings"]:
        ad_id = local_ad["local_photos_dir"]
        target_ad = fresh_active.get(ad_id)
        if target_ad:
            for key in ["views", "status", "url", "date_created"]:
                if key in local_ad:
                    target_ad[key] = local_ad[key]
                    
    assert fresh_data["active_listings"][0]["views"] == 25

@patch("app.load_data")
def test_ai_improve_missing_key(mock_load_data, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": ""})
    res = client.post("/api/ai/improve", json={"text": "Ahoj", "field": "description"})
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Chybí Gemini API klíč" in data["message"]

@patch("app.load_data")
@patch("requests.post")
def test_ai_improve_api_error(mock_post, mock_load_data, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": "valid_key_dummy"})
    
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "API key not valid"
    mock_post.return_value = mock_response
    
    res = client.post("/api/ai/improve", json={"text": "Popis", "field": "description"})
    assert res.status_code == 403
    data = json.loads(res.data)
    assert "Chyba Gemini API" in data["message"]
