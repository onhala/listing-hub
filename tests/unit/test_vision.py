import io
import json
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from listing_hub.ai.vision import prepare_image_for_gemini, analyze_photos_with_vision

def create_dummy_image_bytes(width=100, height=100, color="blue") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_prepare_image_for_gemini():
    raw_bytes = create_dummy_image_bytes(2000, 1500)
    b64_str, mime = prepare_image_for_gemini(raw_bytes, max_size=(800, 800))
    assert mime == "image/jpeg"
    assert len(b64_str) > 0

def test_analyze_photos_missing_api_key():
    img_bytes = create_dummy_image_bytes()
    success, data, msg = analyze_photos_with_vision([img_bytes], api_key="")
    assert not success
    assert "Chybí Gemini API klíč" in msg

def test_analyze_photos_missing_images():
    success, data, msg = analyze_photos_with_vision([], api_key="dummy_key")
    assert not success
    assert "Nebyly přiloženy žádné fotografie" in msg

@patch("requests.post")
@patch("listing_hub.ai.advisor.analyze_bazos_prices")
def test_analyze_photos_success(mock_advisor, mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_json_payload = {
        "item_identification": {
            "brand": "DeWalt",
            "model": "DCD796",
            "full_name": "Aku příklepová vrtačka DeWalt DCD796 18V XR",
            "category_bazos": "dum.bazos.cz / Nářadí",
            "condition": "used_good"
        },
        "titles": [
            "Aku příklepová vrtačka DeWalt DCD796 18V XR + 2x aku (tento nadpis je záměrně velmi dlouhý aby překročil padesát znaků a otestoval sanitaci)",
            "DeWalt DCD796 bezuhlíková aku vrtačka",
            "Sada DeWalt DCD796 s kufrem TSTAK"
        ],
        "recommended_title": "Aku příklepová vrtačka DeWalt DCD796 18V XR + 2x aku",
        "description": "Prodám aku vrtačku DeWalt DCD796...",
        "best_cover_photo_index": 0,
        "quality_tips": ["Fotky jsou kvalitní."]
    }
    
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": f"```json\n{json.dumps(mock_json_payload)}\n```"}]
            }
        }]
    }
    mock_post.return_value = mock_response
    
    mock_advisor.return_value = {
        "total_found": 5,
        "prices_count": 5,
        "statistics": {"median": 2500, "suggested_fair": 2500},
        "listings": []
    }
    
    img_bytes = create_dummy_image_bytes()
    success, data, msg = analyze_photos_with_vision([img_bytes], user_notes="pěkný stav", api_key="dummy_key")
    
    assert success
    assert msg == ""
    assert data["item_identification"]["brand"] == "DeWalt"
    # All titles should be <= 50 chars
    for t in data["titles"]:
        assert len(t) <= 50
    assert len(data["recommended_title"]) <= 50
    assert "market_analysis" in data
    assert data["market_analysis"]["statistics"]["median"] == 2500

@patch("requests.post")
def test_analyze_photos_api_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden / Quota Exceeded"
    mock_post.return_value = mock_response
    
    img_bytes = create_dummy_image_bytes()
    success, data, msg = analyze_photos_with_vision([img_bytes], api_key="dummy_key", run_market_advisor=False)
    
    assert not success
    assert "Chyba Gemini Vision API" in msg

def test_normalize_vision_data_flat_czech_keys():
    from listing_hub.ai.vision import normalize_vision_data
    raw = {
        "znacka": "Bosch",
        "model": "GSR 12V-15",
        "stav": "Použité, funkční",
        "nadpisy": ["Aku šroubovák Bosch GSR 12V-15"],
        "popis": "Prodám aku vrtačku Bosch se dvěma bateriemi.",
        "cena": "1200"
    }
    normalized = normalize_vision_data(raw, total_photos=3)
    assert normalized["item_identification"]["brand"] == "Bosch"
    assert normalized["item_identification"]["model"] == "GSR 12V-15"
    assert normalized["item_identification"]["full_name"] == "Bosch GSR 12V-15"
    assert normalized["item_identification"]["condition_cz"] == "Použité, funkční"
    assert normalized["recommended_title"] == "Aku šroubovák Bosch GSR 12V-15"
    assert "Aku šroubovák Bosch GSR 12V-15" in normalized["titles"]
    assert "Prodám aku vrtačku" in normalized["description"]
    assert normalized["estimated_price_czk"] == 1200
    assert normalized["best_cover_photo_index"] == 0

def test_normalize_vision_data_empty_fallback():
    from listing_hub.ai.vision import normalize_vision_data
    normalized = normalize_vision_data({}, total_photos=1)
    assert normalized["item_identification"]["condition_cz"] == "Zachovalý stav"
    assert len(normalized["titles"]) >= 1
    assert normalized["recommended_title"] != ""
    assert normalized["best_cover_photo_index"] == 0
    assert len(normalized["photo_recommendations"]["quality_tips"]) > 0

@patch("requests.post")
@patch("listing_hub.ai.advisor.analyze_bazos_prices")
def test_analyze_photos_custom_model(mock_advisor, mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": json.dumps({"recommended_title": "Test", "titles": ["Test"]})}]
            }
        }]
    }
    mock_post.return_value = mock_response
    mock_advisor.return_value = {"status": "ok"}

    img_bytes = create_dummy_image_bytes()
    success, data, msg = analyze_photos_with_vision([img_bytes], api_key="dummy_key", model="gemini-2.0-flash")
    assert success
    assert mock_post.called
    called_url = mock_post.call_args[0][0]
    assert "models/gemini-2.0-flash:generateContent" in called_url

