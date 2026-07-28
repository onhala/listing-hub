import os
import json
import sys
from pathlib import Path

# Kořen projektu
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent

# Sjednocené složky pro data
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
PHOTOS_DIR = PROJECT_ROOT / "photos"

# Automatické vytvoření složek
for directory in [CONFIG_DIR, DATA_DIR, PHOTOS_DIR]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Chyba při vytváření složky {directory}: {e}", file=sys.stderr)

# Cesty k datovým souborům
CONFIG_PATH = CONFIG_DIR / "config.json"
SESSION_STATE_PATH = CONFIG_DIR / "session.json"

# Kontrola a automatická oprava práv pro zápis
def check_write_permissions():
    for name, directory in [("Konfigurace", CONFIG_DIR), ("Data", DATA_DIR), ("Fotografie", PHOTOS_DIR)]:
        test_file = directory / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            # Pokusíme se automaticky opravit práva složky na 777
            try:
                os.chmod(directory, 0o777)
                test_file.touch()
                test_file.unlink()
                print(f"✅ Automaticky opravena přístupová práva pro složku {name} ({directory})", file=sys.stderr)
            except Exception as fix_err:
                print(f"❌ KRITICKÁ CHYBA: Složka {name} ({directory}) není zapisovatelná: {e}. Nepodařilo se automaticky opravit práva ({fix_err}). Spusťte na serveru: chmod -R 777 {directory}", file=sys.stderr)

check_write_permissions()

def load_user_config() -> dict:
    """Načte uživatelskou konfiguraci ze souboru (z klíče 'user' nebo kořene)."""
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
            data = json.load(f)
            return data.get("user", data)
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
