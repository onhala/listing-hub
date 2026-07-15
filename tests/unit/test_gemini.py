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

