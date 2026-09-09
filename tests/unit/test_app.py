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

def test_version_check_endpoint(client):
    res = client.get("/api/version/check?force=1")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert "status" in data
    assert "app_version" in data
    assert "local" in data
    assert "latest" in data
    assert "update_available" in data

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

@patch("app.load_data")
def test_api_analyze_photos_missing_key(mock_load_data, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": ""})
    res = client.post("/api/ai/analyze-photos", json={"photos_dir": "dummy"})
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Chybí Gemini API klíč" in data["message"]

@patch("app.load_data")
@patch("app.analyze_photos_with_vision")
def test_api_analyze_photos_success(mock_vision, mock_load_data, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": "dummy_key"})
    mock_vision.return_value = (True, {
        "recommended_title": "Test Title",
        "description": "Test Desc",
        "titles": ["Test Title"]
    }, "")

    import io
    data = {
        "photos": (io.BytesIO(b"fake_image_bytes"), "test.jpg"),
        "notes": "Poznamka"
    }
    res = client.post("/api/ai/analyze-photos", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    res_data = json.loads(res.data)
    assert res_data["status"] == "success"
    assert res_data["data"]["recommended_title"] == "Test Title"

@patch("app.db.save_listing")
def test_api_create_listing_with_photos(mock_save_listing, client, tmp_path):
    import io
    data = {
        "title": "Aku vrtačka Bosch 18V",
        "price": 1500,
        "category": "Nářadí",
        "description": "Plně funkční",
        "photos": [(io.BytesIO(b"dummy_img_1"), "f1.jpg"), (io.BytesIO(b"dummy_img_2"), "f2.jpg")]
    }
    res = client.post("/api/listings/create-with-photos", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    res_data = json.loads(res.data)
    assert res_data["status"] == "success"
    assert res_data["ad"]["title"] == "Aku vrtačka Bosch 18V"
    assert mock_save_listing.called

def test_api_create_listing_with_photos_default_title(client):
    res = client.post("/api/listings/create-with-photos", data={"price": 100}, content_type="multipart/form-data")
    assert res.status_code == 200
    res_data = json.loads(res.data)
    assert res_data["ad"]["title"] == "Nový inzerát"

@patch("app.load_data")
def test_truenas_upgrade_missing_config(mock_load_data, client):
    mock_load_data.return_value = ({}, {})
    with patch.dict("os.environ", {"TRUENAS_URL": "", "TRUENAS_API_KEY": "", "WATCHTOWER_WEBHOOK_URL": ""}):
        res = client.post("/api/version/truenas-upgrade")
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "není nakonfigurován" in data["message"]

@patch("app.load_data")
@patch("requests.post")
def test_truenas_upgrade_success_truenas_api(mock_post, mock_load_data, client):
    mock_load_data.return_value = ({}, {"truenas_url": "http://truenas.local", "truenas_api_key": "dummy_key"})
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_post.return_value = mock_res

    res = client.post("/api/version/truenas-upgrade")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert "úspěšně předán TrueNAS" in data["message"]
    assert mock_post.called

@patch("app.load_data")
@patch("requests.post")
def test_truenas_upgrade_watchtower_webhook(mock_post, mock_load_data, client):
    mock_load_data.return_value = ({}, {})
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_post.return_value = mock_res

    with patch.dict("os.environ", {"WATCHTOWER_WEBHOOK_URL": "http://watchtower:8080/v1/update", "WATCHTOWER_TOKEN": "secret"}):
        res = client.post("/api/version/truenas-upgrade")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "success"
        assert "Watchtower" in data["message"]

@patch("app.db.get_db_connection")
@patch("app.load_data")
def test_analyze_existing_photos_not_found(mock_load_data, mock_get_conn, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": "dummy_key"})
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    res = client.post("/api/ai/analyze-existing/non_existent_id")
    assert res.status_code == 404
    data = json.loads(res.data)
    assert "Inzerát nebyl nalezen" in data["message"]

@patch("app.db.get_db_connection")
@patch("app.load_data")
@patch("app.analyze_photos_with_vision")
@patch("os.path.isdir")
@patch("os.listdir")
def test_analyze_existing_photos_success(mock_listdir, mock_isdir, mock_vision, mock_load_data, mock_get_conn, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": "dummy_key"})
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "local_photos_dir": "photos/item123",
        "title": "Stůl",
        "notes": ""
    }
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    mock_isdir.return_value = True
    mock_listdir.return_value = ["foto_1.jpg"]
    mock_vision.return_value = (True, {"recommended_title": "Analyzovaný stůl", "titles": []}, "")

    from unittest.mock import mock_open
    with patch("builtins.open", mock_open(read_data=b"fake_jpeg_bytes")):
        with patch("app.resolve_photos_dir", return_value="/tmp/photos/item123"):
            res = client.post("/api/ai/analyze-existing/item123")
            assert res.status_code == 200
            data = json.loads(res.data)
            assert data["status"] == "success"
            assert data["data"]["recommended_title"] == "Analyzovaný stůl"
