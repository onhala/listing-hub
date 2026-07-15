import os
import json
from pathlib import Path

# Kořen projektu
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent

# Cesty k datovým souborům
CONFIG_PATH = PROJECT_ROOT / "bazos_config.json"
SESSION_STATE_PATH = PROJECT_ROOT / "bazos_session.json"
PHOTOS_DIR = PROJECT_ROOT / "photos"

def load_user_config() -> dict:
    """Načte uživatelskou konfiguraci ze souboru."""
    if not CONFIG_PATH.exists():
        # Pokud neexistuje, vrátí prázdnou šablonu
        return {
            "jmeno": "",
            "email": "",
            "phone": "",
            "psc": "",
            "default_ad_password_b64": "aGVzbG8xMjM=",
            "gemini_api_key": ""
        }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_user_config(config: dict) -> bool:
    """Uloží uživatelskou konfiguraci."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
