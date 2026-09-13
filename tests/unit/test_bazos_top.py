"""
Unit tests pro Bazoš TOP status feature.
Pokrývá: parsování ztop v scraperu, parsování data expirace v bazos_portal,
DB migrace/persistence a repost modal bezpečnostní logiku (Python strana).
"""
import re
import sqlite3
import uuid
import pytest
from datetime import date, timedelta
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _parse_top_from_title_attr(title_attr: str):
    """Miniaturní kopie parsovací logiky z bazos_portal.fetch_bazos_ad_details."""
    result = {"is_top": False, "top_expires_at": None, "top_info": None}
    if not title_attr:
        return result
    result["is_top"] = True
    result["top_info"] = title_attr
    exp_match = re.search(r"Platí do (\d{1,2})\.(\d{1,2})\.\s*(\d{4})", title_attr)
    if exp_match:
        day, month, year = exp_match.groups()
        result["top_expires_at"] = f"{year}-{int(month):02d}-{int(day):02d}"
    return result


def _is_top_expired(top_expires_at: str) -> bool:
    """Python verze isTopExpired z app.js pro backend testy."""
    if not top_expires_at:
        return True
    try:
        exp_date = date.fromisoformat(top_expires_at)
        return exp_date < date.today()
    except ValueError:
        return True


# ──────────────────────────────────────────────
# Test 1: scraper.py – parsování ztop z HTML listingu
# ──────────────────────────────────────────────

def _make_listing_html(with_top: bool = True, top_title: str = "TOP 1x Platí do 20.9. 2026") -> str:
    top_span = f'<span class="ztop" title="{top_title}">TOP</span>' if with_top else ""
    return f"""
    <div class="inzeraty">
        <div class="nadpis"><a href="https://auto.bazos.cz/inzerat/223514742/arteon.htm">VW Arteon</a></div>
        <div class="inzeratycena">450000 Kč</div>
        <div class="inzeratyview">1234</div>
        <div class="velikost10"> - {top_span} - [13.9. 2026]</div>
    </div>
    """


def test_scraper_detects_top_status():
    from listing_hub.portals.bazos.scraper import scrape_listings_from_html
    html = _make_listing_html(with_top=True)
    results = scrape_listings_from_html(html)
    assert len(results) == 1
    ad = results[0]
    assert ad["is_top"] is True
    assert ad["top_expires_at"] == "2026-09-20"
    assert "Platí do 20.9. 2026" in ad["top_info"]
    assert ad["top_count"] == 1


def test_scraper_no_top_when_missing():
    from listing_hub.portals.bazos.scraper import scrape_listings_from_html
    html = _make_listing_html(with_top=False)
    results = scrape_listings_from_html(html)
    assert len(results) == 1
    ad = results[0]
    assert ad["is_top"] is False
    assert ad["top_expires_at"] is None
    assert ad["top_info"] is None


def test_scraper_top_count_from_title():
    from listing_hub.portals.bazos.scraper import scrape_listings_from_html
    html = _make_listing_html(with_top=True, top_title="TOP 3x Platí do 1.12. 2026")
    results = scrape_listings_from_html(html)
    assert results[0]["top_count"] == 3
    assert results[0]["top_expires_at"] == "2026-12-01"


# ──────────────────────────────────────────────
# Test 2: Regex parsování expirace
# ──────────────────────────────────────────────

@pytest.mark.parametrize("title_attr,expected_date", [
    ("TOP 1x Platí do 20.9. 2026", "2026-09-20"),
    ("TOP 2x Platí do 1.12. 2026", "2026-12-01"),
    ("TOP 1x Platí do 5.1. 2027", "2027-01-05"),
    ("TOP 1x Platí do 31.3. 2026", "2026-03-31"),
])
def test_top_expiry_regex_parsing(title_attr, expected_date):
    result = _parse_top_from_title_attr(title_attr)
    assert result["is_top"] is True
    assert result["top_expires_at"] == expected_date


def test_top_expiry_regex_no_match():
    result = _parse_top_from_title_attr("TOP bez data")
    assert result["is_top"] is True
    assert result["top_expires_at"] is None


def test_top_expiry_empty_string():
    result = _parse_top_from_title_attr("")
    assert result["is_top"] is False
    assert result["top_expires_at"] is None


# ──────────────────────────────────────────────
# Test 3: DB migrace a persistence
# ──────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Dočasná SQLite DB pro izolované DB testy."""
    db_path = tmp_path / "test_listings.db"
    import listing_hub.core.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    # Reinicializace DB
    db_module.init_db()
    yield db_module
    # Cleanup je automatický díky tmp_path


def test_portal_states_has_top_columns(tmp_db):
    """Ověří, že tabulka portal_states po init_db obsahuje is_top, top_expires_at, top_info."""
    conn = tmp_db.get_db_connection()
    cursor = conn.execute("PRAGMA table_info(portal_states)")
    col_names = {row["name"] for row in cursor.fetchall()}
    conn.close()
    assert "is_top" in col_names
    assert "top_expires_at" in col_names
    assert "top_info" in col_names


def test_save_and_retrieve_top_status(tmp_db):
    """Uloží inzerát s TOP statusem a ověří, že se správně načte přes get_all_listings."""
    listing_id = str(uuid.uuid4())
    listing_data = {
        "id": listing_id,
        "title": "VW Arteon TOP test",
        "description": "Test",
        "price": 450000,
        "category": "auto.bazos.cz",
        "condition": "Aktivní",
        "local_photos_dir": "/tmp",
        "location": "Test",
        "notes": "",
        "ad_password_b64": "aGVzbG8xMjM=",
        "bookmarklet_uri": "",
        "days_old": 0,
        "created_at": "2026-09-13",
        "target_bazos": 1,
        "target_aukro": 0,
    }
    portal_state = {
        "bazos": {
            "portal_item_id": "223514742",
            "url": "https://auto.bazos.cz/inzerat/223514742/arteon.htm",
            "status": "Aktivní",
            "views": 500,
            "is_top": True,
            "top_expires_at": "2026-09-20",
            "top_info": "TOP 1x Platí do 20.9. 2026",
        }
    }
    tmp_db.save_listing(listing_data, portal_state)

    all_listings = tmp_db.get_all_listings()
    saved = next((l for l in all_listings if l["id"] == listing_id), None)
    assert saved is not None
    assert saved["is_top"] is True
    assert saved["top_expires_at"] == "2026-09-20"
    assert saved["top_info"] == "TOP 1x Platí do 20.9. 2026"


def test_save_listing_without_top(tmp_db):
    """Inzerát bez TOP musí mít is_top=False a prázdné top pole."""
    listing_id = str(uuid.uuid4())
    listing_data = {
        "id": listing_id,
        "title": "Bez TOP",
        "description": "Test",
        "price": 1000,
        "category": "ostatni.bazos.cz",
        "condition": "Aktivní",
        "local_photos_dir": "/tmp",
        "location": "Test",
        "notes": "",
        "ad_password_b64": "aGVzbG8xMjM=",
        "bookmarklet_uri": "",
        "days_old": 5,
        "created_at": "2026-09-08",
        "target_bazos": 1,
        "target_aukro": 0,
    }
    portal_state = {
        "bazos": {
            "portal_item_id": "999999999",
            "url": "https://ostatni.bazos.cz/inzerat/999999999/test.htm",
            "status": "Aktivní",
            "views": 10,
            "is_top": False,
            "top_expires_at": None,
            "top_info": None,
        }
    }
    tmp_db.save_listing(listing_data, portal_state)
    by_id = tmp_db.get_listing_by_id(listing_id)
    assert by_id is not None
    assert by_id["is_top"] is False
    assert by_id["top_expires_at"] is None


# ──────────────────────────────────────────────
# Test 4: Bezpečnostní logika expirace (Python verze)
# ──────────────────────────────────────────────

def test_is_top_expired_future():
    future = (date.today() + timedelta(days=7)).isoformat()
    assert _is_top_expired(future) is False


def test_is_top_expired_past():
    past = (date.today() - timedelta(days=1)).isoformat()
    assert _is_top_expired(past) is True


def test_is_top_expired_today():
    """TOP expirující dnes je ještě platný (stejný den jako dnes = ne dřívější)."""
    today = date.today().isoformat()
    # today == today, ne today < today → není expirovaný
    assert _is_top_expired(today) is False


def test_is_top_expired_none():
    assert _is_top_expired(None) is True


def test_is_top_expired_invalid():
    assert _is_top_expired("not-a-date") is True


# ──────────────────────────────────────────────
# Test 5: fetch_bazos_ad_details vrací TOP pole (unit test bez sítě)
# ──────────────────────────────────────────────

def test_fetch_bazos_ad_details_top_parsing(monkeypatch):
    """Mockuje HTTP odpověď a ověří, že fetch_bazos_ad_details správně extrahuje TOP metadata."""
    import urllib.request
    from listing_hub.portals.bazos import bazos_portal

    mock_html = """
    <html><body>
    <h1>VW Arteon</h1>
    <div class="popisdetail">Krásné auto v top stavu.</div>
    <table>
      <tr><td>Lokalita:</td><td>Rožnov u Českých Budějovic</td></tr>
      <tr><td>Cena:</td><td>450&nbsp;000 Kč</td></tr>
    </table>
    <span class="velikost10"> - <span class="ztop" title="TOP 1x Platí do 20.9. 2026">TOP</span> - [13.9. 2026]</span>
    </body></html>
    """

    class _FakeResponse:
        def geturl(self): return "https://auto.bazos.cz/inzerat/223514742/arteon.htm"
        def read(self): return mock_html.encode("utf-8")
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: _FakeResponse())

    result = bazos_portal.fetch_bazos_ad_details("https://auto.bazos.cz/inzerat/223514742/arteon.htm")
    assert result["is_top"] is True
    assert result["top_expires_at"] == "2026-09-20"
    assert "Platí do 20.9. 2026" in result["top_info"]
    assert result["is_deleted"] is False
