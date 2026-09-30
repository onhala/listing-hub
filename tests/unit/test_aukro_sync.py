import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from listing_hub.portals.aukro.aukro_portal import AukroPortal
from listing_hub.portals.scrapers.universal import _extract_domain_specific
from listing_hub.core import db
from app import app


@pytest.fixture
def aukro_portal():
    return AukroPortal()


def test_aukro_portal_properties(aukro_portal):
    assert aukro_portal.name == "aukro"
    assert aukro_portal.display_name == "Aukro.cz"
    assert "aukro.cz" in aukro_portal.supported_domains
    assert "www.aukro.cz" in aukro_portal.supported_domains


def test_extract_item_id_from_url(aukro_portal):
    assert aukro_portal.extract_item_id_from_url("https://aukro.cz/vintage-hodinky-prim-7023849102") == "7023849102"
    assert aukro_portal.extract_item_id_from_url("https://aukro.cz/nabidka/7082098064") == "7082098064"
    assert aukro_portal.extract_item_id_from_url("https://aukro.cz/item-name-7082098064?sort=price") == "7082098064"
    assert aukro_portal.extract_item_id_from_url("https://example.com/other") is None
    assert aukro_portal.extract_item_id_from_url("") is None


def test_universal_scraper_aukro_displayed_count():
    html_displayed = '<script>{"displayedCount": 58}</script>'
    assert _extract_domain_specific("https://aukro.cz/nabidka/7082098064", html_displayed) == 58

    html_views_count = '<script>{"viewsCount": 12}</script>'
    assert _extract_domain_specific("https://aukro.cz/nabidka/7082098064", html_views_count) == 12

    html_text = '<p>Celkem 99 zobrazení</p>'
    assert _extract_domain_specific("https://aukro.cz/nabidka/7082098064", html_text) == 99


def test_fetch_user_active_listings_mocked(aukro_portal):
    mock_auk_cache = {
        "aukCache": {
            "POST /backend-web/api/offers/searchItemsCommon page=0&size=60 {}": {
                "b": {
                    "content": [
                        {
                            "itemId": 7099999999,
                            "itemName": "Starožitné hodiny pendlovky",
                            "seoUrl": "starozitne-hodiny-pendlovky",
                            "price": {"amount": 1500, "currency": "CZK"},
                            "buyNowPrice": {"amount": 2000, "currency": "CZK"},
                            "startingTime": "2026-09-01T10:00:00+02:00",
                            "endingTime": "2026-10-01T10:00:00+02:00",
                            "itemState": "ACTIVE",
                            "titleImageUrl": "https://cdn.aukro.cz/img1.jpg",
                            "location": "Praha",
                            "postcode": "110 00",
                            "watchersCount": 5,
                            "auction": False
                        }
                    ]
                }
            }
        }
    }
    mock_html = f"<html><body><script>{json.dumps(mock_auk_cache)}</script></body></html>"

    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_html.encode("utf-8")
        mock_url.return_value.__enter__.return_value = mock_resp

        items = aukro_portal.fetch_user_active_listings("test_seller")
        assert len(items) == 1
        item = items[0]
        assert item["item_id"] == "7099999999"
        assert item["title"] == "Starožitné hodiny pendlovky"
        assert item["price"] == 1500
        assert item["watchers"] == 5
        assert item["url"] == "https://aukro.cz/starozitne-hodiny-pendlovky-7099999999"


def test_fetch_offer_detail_mocked(aukro_portal):
    mock_detail = {
        "displayedCount": 42,
        "watchingUserCount": 7,
        "biddersCount": 3,
        "descriptionStripped": "Krásný funkční stav po generálce.",
        "endingTime": "2026-10-15T18:00:00+02:00",
        "state": "ACTIVE",
        "price": {"amount": 2500, "currency": "CZK"},
        "itemImages": [
            {
                "sizes": {
                    "ORIGINAL": {"url": "https://cdn.aukro.cz/original.jpg"},
                    "LARGE": {"url": "https://cdn.aukro.cz/large.jpg"}
                }
            }
        ]
    }

    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_detail).encode("utf-8")
        mock_url.return_value.__enter__.return_value = mock_resp

        detail = aukro_portal.fetch_offer_detail("7099999999")
        assert detail["views"] == 42
        assert detail["watchers"] == 7
        assert detail["bidders"] == 3
        assert detail["description"] == "Krásný funkční stav po generálce."
        assert detail["price"] == 2500
        assert detail["images"] == ["https://cdn.aukro.cz/original.jpg"]


def test_sync_listings_empty_config(aukro_portal):
    res = aukro_portal.sync_listings({})
    assert res == []


def test_sync_listings_flow(tmp_path, monkeypatch, aukro_portal):
    # Isolated DB
    test_db_path = tmp_path / "test_listings.db"
    monkeypatch.setattr(db, "DB_PATH", test_db_path)
    db.init_db()

    # Pre-populate an existing listing that should be matched
    existing_id = "test-ad-1"
    existing_listing = {
        "id": existing_id,
        "title": "Starožitné hodiny pendlovky",
        "description": "Původní popis",
        "price": 1000,
        "category": "Starožitnosti",
        "condition": "Aktivní",
        "local_photos_dir": str(tmp_path / "photos_1"),
        "location": "Český Krumlov",
        "notes": "",
        "ad_password_b64": "",
        "bookmarklet_uri": "",
        "days_old": 5,
        "created_at": "2026-09-20",
        "target_bazos": 1,
        "target_aukro": 0
    }
    db.save_listing(existing_listing, {})

    # Mock fetch_user_active_listings returning:
    # 1. Starožitné hodiny (should match existing_listing)
    # 2. Nová položka (should be imported as new listing)
    mock_active_items = [
        {
            "item_id": "7099999999",
            "title": "Starožitné hodiny pendlovky",
            "url": "https://aukro.cz/starozitne-hodiny-pendlovky-7099999999",
            "price": 1500,
            "starting_time": "2026-09-01T10:00:00+02:00",
            "ending_time": "2026-10-01T10:00:00+02:00",
            "item_state": "ACTIVE",
            "title_image_url": "https://cdn.aukro.cz/img1.jpg",
            "location": "Český Krumlov",
            "postcode": "381 01",
            "watchers": 5,
            "is_auction": False
        },
        {
            "item_id": "7088888888",
            "title": "Retro rádio Tesla Talisman",
            "url": "https://aukro.cz/retro-radio-tesla-talisman-7088888888",
            "price": 2200,
            "starting_time": "2026-09-25T12:00:00+02:00",
            "ending_time": "2026-10-05T12:00:00+02:00",
            "item_state": "ACTIVE",
            "title_image_url": "https://cdn.aukro.cz/radio.jpg",
            "location": "Český Krumlov",
            "postcode": "381 01",
            "watchers": 2,
            "is_auction": False
        }
    ]

    mock_detail = {
        "views": 25,
        "watchers": 5,
        "bidders": 0,
        "description": "Kompletní detailní popis z Aukra.",
        "ending_time": "2026-10-01T10:00:00+02:00",
        "state": "ACTIVE",
        "price": 1500,
        "images": []
    }

    monkeypatch.setattr(aukro_portal, "fetch_user_active_listings", lambda u: mock_active_items)
    monkeypatch.setattr(aukro_portal, "fetch_offer_detail", lambda item_id: mock_detail)
    monkeypatch.setattr(aukro_portal, "download_photos_if_missing", lambda urls, d: None)

    # Run sync
    synced = aukro_portal.sync_listings({"aukro_username": "ondrejhala"})
    assert len(synced) == 2

    # Verify existing ad was updated
    all_ads = db.get_all_listings()
    assert len(all_ads) == 2

    matched_ad = next(a for a in all_ads if a["id"] == existing_id)
    assert matched_ad["price"] == 1500
    assert matched_ad["target_aukro"] == 1
    assert "aukro" in matched_ad["portal_states"]
    assert matched_ad["portal_states"]["aukro"]["views"] == 25
    assert matched_ad["portal_states"]["aukro"]["top_info"] == "Sleduje: 5"

    # Verify new ad was imported
    new_ad = next(a for a in all_ads if a["id"] != existing_id)
    assert new_ad["title"] == "Retro rádio Tesla Talisman"
    assert new_ad["target_aukro"] == 1
    assert new_ad["category"] == "Aukro"
    assert new_ad["portal_states"]["aukro"]["portal_item_id"] == "7088888888"


def test_api_sync_aukro_endpoint(monkeypatch):
    client = app.test_client()

    # 1. Missing username returns warning
    monkeypatch.setattr("listing_hub.core.config.load_user_config", lambda: {"aukro_username": ""})
    res = client.post("/api/sync/aukro")
    assert res.status_code == 400
    assert res.get_json()["status"] == "warning"

    # 2. Configured username executes sync
    mock_sync_return = [{"item_id": "123", "title": "Test"}]
    with patch("listing_hub.portals.aukro.aukro_portal.AukroPortal.sync_listings", return_value=mock_sync_return):
        monkeypatch.setattr("listing_hub.core.config.load_user_config", lambda: {"aukro_username": "ondrejhala"})
        res2 = client.post("/api/sync/aukro")
        assert res2.status_code == 200
        data = res2.get_json()
        assert data["status"] == "success"
        assert len(data["data"]) == 1


def test_fetch_ad_details(monkeypatch):
    aukro_portal = AukroPortal()

    # Invalid URL
    res_invalid = aukro_portal.fetch_ad_details("https://example.com/item")
    assert res_invalid["is_active"] is False
    assert "Neplatná" in res_invalid["error"]

    # Valid URL with mocked detail
    mock_detail = {
        "views": 42,
        "watchers": 3,
        "bidders": 0,
        "description": "Popis",
        "ending_time": "2026-10-01T10:00:00+02:00",
        "state": "ACTIVE",
        "price": 990,
        "images": []
    }
    monkeypatch.setattr(aukro_portal, "fetch_offer_detail", lambda item_id: mock_detail)
    res_valid = aukro_portal.fetch_ad_details("https://aukro.cz/polozka-7082098064")
    assert res_valid["is_active"] is True
    assert res_valid["status"] == "Aktivní"
    assert res_valid["views"] == 42
    assert res_valid["price"] == 990
    assert res_valid["watchers"] == 3

