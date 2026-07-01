import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

# Přidání aktuálního adresáře do sys.path pro importy
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app, count_photos
from post_to_bazos import parse_bazos_date

class TestBazosBackend(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    # 1. TEST PARSOVÁNÍ DAT Z BAZOŠE (post_to_bazos.py)
    def test_parse_bazos_date(self):
        from datetime import datetime, timedelta
        today_str = datetime.today().strftime("%Y-%m-%d")
        yesterday_str = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Test relativních českých dat
        self.assertEqual(parse_bazos_date("[Dnes - 12:34]"), today_str)
        self.assertEqual(parse_bazos_date("[Včera]"), yesterday_str)
        
        # Test absolutních dat
        self.assertEqual(parse_bazos_date("[29.6. 2026]"), "2026-06-29")
        self.assertEqual(parse_bazos_date("1.12. 2025"), "2025-12-01")
        
        # Test fallback chování při neplatném datu
        self.assertEqual(parse_bazos_date("neplatne_datum"), today_str)

    # 2. TEST POČÍTÁNÍ FOTEK
    @patch("os.path.isdir")
    @patch("os.listdir")
    def test_count_photos(self, mock_listdir, mock_isdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = ["foto_1.jpg", "foto_2.png", "document.pdf", "readme.txt"]
        
        # Bez vyloučení fotek
        total, included = count_photos("dummy_dir", [])
        self.assertEqual(total, 2)
        self.assertEqual(included, 2)
        
        # S vyloučením jedné fotky
        total, included = count_photos("dummy_dir", ["foto_1.jpg"])
        self.assertEqual(total, 2)
        self.assertEqual(included, 1)

    # 3. TEST API ENDPOINTŮ VERZE (DOCKER VS LOCAL)
    @patch("app.IS_DOCKER", True)
    def test_version_update_blocked_in_docker(self):
        # V Dockeru by měl update vrátit 400 Bad Request
        res = self.app.post("/api/version/update")
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertIn("V Dockeru nelze spustit", data["message"])

    @patch("app.IS_DOCKER", False)
    @patch("subprocess.check_output")
    @patch("os._exit")
    def test_version_update_success_local(self, mock_exit, mock_subprocess):
        mock_subprocess.return_value = "Already up to date."
        
        # Lokálně by měl update projít
        res = self.app.post("/api/version/update")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("Already up to date.", data["message"])

    # 4. TEST SLUČOVACÍ LOGIKY (SAFE MERGE)
    def test_safe_merge_logic_simulation(self):
        # Simulace safe merge chování (monkey-patch v app.py)
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
        
        # Nasimulujeme chování safe merge pro active_listings
        fresh_active = {ad["local_photos_dir"]: ad for ad in fresh_data["active_listings"]}
        for local_ad in local_data["active_listings"]:
            ad_id = local_ad["local_photos_dir"]
            target_ad = fresh_active.get(ad_id)
            if target_ad:
                for key in ["views", "status", "url", "date_created"]:
                    if key in local_ad:
                        target_ad[key] = local_ad[key]
                        
        self.assertEqual(fresh_data["active_listings"][0]["views"], 25)

    # 5. TEST CHYBOVÝCH STAVŮ AI GEMINI
    @patch("app.load_data")
    def test_ai_improve_missing_key(self, mock_load_data):
        mock_load_data.return_value = ({}, {"gemini_api_key": ""})
        
        # Test bez API klíče
        res = self.app.post("/api/ai/improve", json={"text": "Ahoj", "field": "description"})
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertIn("Chybí Gemini API klíč", data["message"])

    @patch("app.load_data")
    @patch("requests.post")
    def test_ai_improve_api_error(self, mock_post, mock_load_data):
        mock_load_data.return_value = ({}, {"gemini_api_key": "valid_key_dummy"})
        
        # Simulace chybové odpovědi od Google API (např. neplatný klíč)
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "API key not valid"
        mock_post.return_value = mock_response
        
        res = self.app.post("/api/ai/improve", json={"text": "Popis", "field": "description"})
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data)
        self.assertIn("Chyba Gemini API", data["message"])

if __name__ == "__main__":
    unittest.main()
