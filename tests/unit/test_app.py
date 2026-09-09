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
def test_api_test_gemini_missing_key(mock_load_data, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": ""})
    res = client.post("/api/ai/test", json={"model": "gemini-2.5-flash", "api_key": ""})
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Chybí Gemini API klíč" in data["message"]

@patch("app.load_data")
@patch("requests.post")
def test_api_test_gemini_success(mock_post, mock_load_data, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": "dummy_saved_key"})
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "OK"}]}}]
    }
    mock_post.return_value = mock_response

    res = client.post("/api/ai/test", json={"model": "gemini-2.5-pro"})
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert data["model"] == "gemini-2.5-pro"
    assert "latency_ms" in data
    assert mock_post.called
    called_url = mock_post.call_args[0][0]
    assert "models/gemini-2.5-pro:generateContent" in called_url

@patch("app.load_data")
@patch("requests.post")
def test_api_test_gemini_error(mock_post, mock_load_data, client):
    mock_load_data.return_value = ({}, {"gemini_api_key": "invalid_key"})
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {"message": "API key not valid. Please pass a valid API key."}
    }
    mock_post.return_value = mock_response

    res = client.post("/api/ai/test", json={"model": "gemini-2.5-flash"})
    assert res.status_code == 400
    data = json.loads(res.data)
    assert data["status"] == "error"
    assert "API key not valid" in data["message"]


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

@patch("app.load_data")
def test_calendar_feed_unauthorized(mock_load_data, client):
    mock_load_data.return_value = ({}, {"calendar_token": "secret_12345"})
    res = client.get("/api/calendar/feed.ics?token=wrong_token")
    assert res.status_code == 403

@patch("app.db.get_all_listings")
@patch("app.load_data")
def test_calendar_feed_success(mock_load_data, mock_get_listings, client):
    mock_load_data.return_value = ({}, {"calendar_token": "secret_12345"})
    mock_get_listings.return_value = [
        {
            "id": "item1",
            "title": "Kolo Author",
            "price": 5000,
            "status": "Aktivní",
            "created_at": "2026-07-15",
            "portal_states": {"bazos": {"url": "https://sport.bazos.cz/inzerat/1/kolo.php"}}
        }
    ]

    res = client.get("/api/calendar/feed.ics?token=secret_12345")
    assert res.status_code == 200
    assert res.mimetype == "text/calendar"
    text = res.data.decode("utf-8")
    assert "BEGIN:VCALENDAR" in text
    assert "Kolo Author" in text
    assert "https://sport.bazos.cz/inzerat/1/kolo.php" in text

def test_photo_edit_preview_with_b64(client):
    import io
    import base64
    from PIL import Image
    img = Image.new("RGB", (50, 50), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    res = client.post("/api/photos/edit/preview", json={
        "image_b64": b64_str,
        "operations": [{"type": "blur_box", "box": [0.1, 0.1, 0.9, 0.9], "radius": 5}]
    })
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert data["data_url"].startswith("data:image/jpeg;base64,")

def test_photo_edit_save(client, tmp_path):
    import io
    from PIL import Image
    test_dir = tmp_path / "photos" / "test_item"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "foto_1.jpg"

    img = Image.new("RGB", (50, 50), color="blue")
    img.save(str(test_file), format="JPEG")

    with patch("app.resolve_photos_dir", return_value=str(test_dir)):
        res = client.post("/api/photos/edit/save", json={
            "photos_dir": str(test_dir),
            "filename": "foto_1.jpg",
            "operations": [{"type": "blur_box", "box": [0.2, 0.2, 0.8, 0.8], "radius": 5}]
        })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "success"
        assert test_file.is_file()

def test_submit_sms_code_empty(client):
    res = client.post("/api/sms_code", json={"code": ""})
    assert res.status_code == 400
    data = json.loads(res.data)
    assert data["status"] == "error"

def test_submit_sms_code_success(client):
    with patch("app.session_manager.run_on_worker", return_value=True), \
         patch("app.session_manager.running", True), \
         patch("app.session_manager.page", MagicMock(is_closed=lambda: False)):
        res = client.post("/api/sms_code", json={"code": "123 456"})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "ok"
        assert data["submitted"] is True

def test_submit_sms_code_unfound(client):
    with patch("app.session_manager.run_on_worker", return_value=False), \
         patch("app.session_manager.running", True), \
         patch("app.session_manager.page", MagicMock(is_closed=lambda: False)):
        res = client.post("/api/sms_code", json={"code": "999888"})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "error"
        assert data["submitted"] is False

