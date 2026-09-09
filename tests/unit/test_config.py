import pytest
import json
from pathlib import Path
from unittest.mock import patch
from listing_hub.core.config import load_user_config, save_user_config

def test_load_user_config_defaults(tmp_path):
    dummy_path = tmp_path / "non_existent_config.json"
    with patch("listing_hub.core.config.CONFIG_PATH", dummy_path):
        cfg = load_user_config()
        assert "default_ad_password_b64" in cfg
        assert cfg["default_ad_password_b64"] == "aGVzbG8xMjM="

def test_save_and_load_user_config(tmp_path):
    dummy_path = tmp_path / "test_config.json"
    with patch("listing_hub.core.config.CONFIG_PATH", dummy_path):
        test_data = {
            "name": "Ondřej Hála",
            "email": "ondrej.hala@roboton.com",
            "phone": "605207116",
            "truenas_url": "http://192.168.1.50",
            "truenas_api_key": "secret_key_123"
        }
        success = save_user_config(test_data)
        assert success is True

        loaded = load_user_config()
        assert loaded["name"] == "Ondřej Hála"
        assert loaded["truenas_url"] == "http://192.168.1.50"
        assert loaded["truenas_api_key"] == "secret_key_123"

def test_save_user_config_error():
    with patch("builtins.open", side_effect=IOError("Permission denied")):
        success = save_user_config({"key": "val"})
        assert success is False
