import pytest
from unittest.mock import patch, MagicMock
from listing_hub.ai.gemini import improve_text_with_gemini

def test_improve_text_with_gemini_missing_api_key():
    success, message = improve_text_with_gemini("ahoj", "title", "improve", "")
    assert not success
    assert "Chybí Gemini API klíč" in message

@patch("requests.post")
def test_improve_text_with_gemini_success_title(mock_post):
    # Mocking successful API response for a title
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "  Vylepšený nadpis inzerátu  "}
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    success, result = improve_text_with_gemini("starý nadpis", "title", "improve", "dummy_key")
    assert success
    assert result == "Vylepšený nadpis inzerátu"

@patch("requests.post")
def test_improve_text_with_gemini_success_suggestions(mock_post):
    # Mocking successful API response for title suggestions
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "1. Nadpis Jedna\n2. Nadpis Dva\n3. Nadpis Tri\n4. Nadpis Ctyri\n5. Nadpis Pet\n"}
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    success, result = improve_text_with_gemini("starý nadpis", "title", "title_suggestions", "dummy_key")
    assert success
    lines = result.split("\n")
    assert len(lines) == 5
    assert lines[0] == "Nadpis Jedna"
    assert lines[4] == "Nadpis Pet"

@patch("requests.post")
def test_improve_text_with_gemini_api_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Invalid request payload"
    mock_post.return_value = mock_response

    success, result = improve_text_with_gemini("nejaký text", "description", "improve", "dummy_key")
    assert not success
    assert "Chyba Gemini API" in result

from listing_hub.ai.gemini import strip_markdown_codeblocks

def test_strip_markdown_codeblocks_html():
    input_text = "```html\n<h1>Výsledek</h1>\n```"
    assert strip_markdown_codeblocks(input_text) == "<h1>Výsledek</h1>"

def test_strip_markdown_codeblocks_json():
    input_text = "```json\n{\n  \"test\": true\n}\n```"
    assert strip_markdown_codeblocks(input_text) == "{\n  \"test\": true\n}"

def test_strip_markdown_codeblocks_plain():
    input_text = "```\nPlain text in block\n```"
    assert strip_markdown_codeblocks(input_text) == "Plain text in block"

def test_strip_markdown_codeblocks_no_wrap():
    input_text = "Just some text without block"
    assert strip_markdown_codeblocks(input_text) == "Just some text without block"

@patch("requests.post")
def test_improve_text_with_gemini_payload_config(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "```html\nVylepšený text\n```"}
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    success, result = improve_text_with_gemini("test text", "description", "improve", "dummy_key")
    assert success
    assert result == "Vylepšený text"

    # Verify request payload details
    assert mock_post.called
    kwargs = mock_post.call_args[1]
    assert "json" in kwargs
    payload = kwargs["json"]
    
    # Check that systemInstruction is populated and correct
    assert "systemInstruction" in payload
    assert payload["systemInstruction"]["parts"][0]["text"].startswith("Jsi AI asistent")
    
    # Check generation config
    assert "generationConfig" in payload
    gen_config = payload["generationConfig"]
    assert gen_config["temperature"] == 0.4
    assert gen_config["maxOutputTokens"] == 4096

@patch("requests.post")
def test_improve_text_with_gemini_custom_model(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Odpověď"}]}}]
    }
    mock_post.return_value = mock_response

    success, result = improve_text_with_gemini("text", "title", "improve", "dummy_key", model="gemini-2.5-pro")
    assert success
    assert mock_post.called
    called_url = mock_post.call_args[0][0]
    assert "models/gemini-2.5-pro:generateContent" in called_url

from listing_hub.ai.gemini import clean_bazos_text

def test_clean_bazos_text_strips_asterisks_and_bullets():
    raw_text = (
        "**POPIS PŘEDMĚTU:**\n"
        "* položka 1 s hvězdičkou\n"
        "* položka 2 s **tučným** textem\n"
        "• položka s puntíkem\n"
        "Běžný text s *kurzívou* a hvězdičkou na konci*\n"
    )
    cleaned = clean_bazos_text(raw_text)
    assert "*" not in cleaned
    assert "•" not in cleaned
    assert "POPIS PŘEDMĚTU:" in cleaned
    assert "- položka 1 s hvězdičkou" in cleaned
    assert "- položka 2 s tučným textem" in cleaned
    assert "- položka s puntíkem" in cleaned
    assert "Běžný text s kurzívou a hvězdičkou na konci" in cleaned

@patch("requests.post")
def test_improve_text_with_gemini_custom_seller_context(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Vylepšený text"}]}}]
    }
    mock_post.return_value = mock_response

    success, result = improve_text_with_gemini(
        "původní text",
        "description",
        "improve",
        "dummy_key",
        seller_context="Férový prodejce z Českého Krumlova"
    )
    assert success
    assert mock_post.called
    json_payload = mock_post.call_args[1]["json"]
    sys_instruction = json_payload["systemInstruction"]["parts"][0]["text"]
    assert "Férový prodejce z Českého Krumlova" in sys_instruction

@patch("requests.post")
def test_improve_text_with_gemini_404_deprecated_model(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "This model models/gemini-2.5-pro is no longer available to new users."
    mock_post.return_value = mock_response

    success, result = improve_text_with_gemini("ahoj", "title", "improve", "dummy_key", model="gemini-2.5-pro")
    assert not success
    assert "již není v Google AI dostupný (Status 404)" in result
    assert "gemini-2.5-flash" in result

from listing_hub.ai.gemini import get_available_gemini_models, DEFAULT_FALLBACK_MODELS, _MODELS_CACHE

def test_get_available_gemini_models_empty_key():
    res = get_available_gemini_models(api_key="", force_refresh=True)
    assert res["is_fallback"] is True
    assert len(res["models"]) == len(DEFAULT_FALLBACK_MODELS)
    model_ids = [m["id"] for m in res["models"]]
    assert "gemini-2.5-flash" in model_ids
    assert "gemini-2.5-pro" not in model_ids
    assert "gemini-3.1-pro-preview" in model_ids

@patch("requests.get")
def test_get_available_gemini_models_api_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                "description": "Fast model",
                "supportedGenerationMethods": ["generateContent", "countTokens"]
            },
            {
                "name": "models/gemini-3.1-pro-preview",
                "displayName": "Gemini 3.1 Pro Preview",
                "description": "Smart frontier model",
                "supportedGenerationMethods": ["generateContent"]
            },
            {
                "name": "models/text-embedding-004",
                "displayName": "Text Embedding",
                "supportedGenerationMethods": ["embedContent"]
            },
            {
                "name": "models/gemini-2.5-pro",
                "displayName": "Gemini 2.5 Pro",
                "supportedGenerationMethods": ["generateContent"]
            },
            {
                "name": "models/imagen-3.0-generate-002",
                "displayName": "Imagen 3",
                "supportedGenerationMethods": ["generateContent"]
            }
        ]
    }
    mock_get.return_value = mock_response

    res = get_available_gemini_models(api_key="valid_test_key_123", force_refresh=True)
    assert res["is_fallback"] is False
    assert len(res["models"]) == 2
    model_ids = [m["id"] for m in res["models"]]
    assert model_ids == ["gemini-2.5-flash", "gemini-3.1-pro-preview"]
    assert "gemini-2.5-pro" not in model_ids
    assert "text-embedding-004" not in model_ids
    assert "imagen-3.0-generate-002" not in model_ids
    assert res["models"][0]["recommended"] is True

@patch("requests.get")
def test_get_available_gemini_models_api_error_fallback(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"
    mock_get.return_value = mock_response

    res = get_available_gemini_models(api_key="forbidden_key_456", force_refresh=True)
    assert res["is_fallback"] is True
    assert len(res["models"]) == len(DEFAULT_FALLBACK_MODELS)

@patch("requests.get")
def test_get_available_gemini_models_caching(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                "supportedGenerationMethods": ["generateContent"]
            }
        ]
    }
    mock_get.return_value = mock_response

    test_key = "cache_test_key_789"
    res1 = get_available_gemini_models(api_key=test_key, force_refresh=True)
    assert mock_get.call_count == 1

    # Second call without force_refresh should hit in-memory cache
    res2 = get_available_gemini_models(api_key=test_key, force_refresh=False)
    assert mock_get.call_count == 1
    assert res1["models"] == res2["models"]
