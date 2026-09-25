"""
Unit tests pro Bazoš Search Rank Tracker a SMS TOP Helper.
Pokrývá:
1. extract_search_keywords
2. check_bazos_search_rank (s mockovaným HTTP)
3. update_listing_portal_rank (DB persistence)
4. API endpointy v app.py (/api/listings/<id>/check_rank a /api/listings/<id>/sms_top_info)
"""
import io
import pytest
import unittest.mock as mock
from unittest.mock import MagicMock, patch
from listing_hub.portals.bazos.rank_tracker import (
    extract_search_keywords,
    check_bazos_search_rank,
    _parse_total_results
)
from listing_hub.core.db import (
    init_db,
    save_listing,
    get_listing_by_id,
    update_listing_portal_rank
)

def test_extract_search_keywords():
    # Odstraní technické specifikace, motorizace a stop-slova
    title1 = "VW Arteon SB R-Line 2.0TSI 206kW 4M Záruka 12/26 ČR"
    assert extract_search_keywords(title1) == "VW Arteon SB"

    title2 = "Aku vrtačka Bosch GSR 18V-50 v kufru"
    assert extract_search_keywords(title2) == "Aku vrtačka Bosch"

    title3 = "Sekačka Hecht 548 s pojezdem TOP stav"
    assert extract_search_keywords(title3) == "Sekačka Hecht"

    # Krátký název zůstane
    title4 = "iPhone 15 Pro"
    assert extract_search_keywords(title4) == "iPhone 15 Pro"

    # Prázdný název
    assert extract_search_keywords("") == ""


def test_parse_total_results():
    html_with_count = '<div class="inzeratynadpis">Zobrazeno 1-20 inzerátů z 49</div>'
    assert _parse_total_results(html_with_count) == 49

    html_no_count = '<div class="inzeratynadpis">Žádný inzerát</div>'
    assert _parse_total_results(html_no_count) is None


def test_check_bazos_search_rank_found_page_1():
    mock_html = """
    <html>
        <body>
            <div class="inzeratynadpis">Zobrazeno 1-20 inzerátů z 15</div>
            <div class="inzeraty inzeratyflex">
                <div class="nadpis"><a href="/inzerat/111111/jiny.htm">Jiný inzerát</a></div>
            </div>
            <div class="inzeraty inzeratyflex">
                <div class="nadpis"><a href="/inzerat/223514742/arteon.htm">VW Arteon SB</a></div>
                <span class="ztop" title="TOP 1x">TOP</span>
            </div>
        </body>
    </html>
    """.encode("utf-8")

    class MockResp:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def read(self):
            return mock_html

    with patch("urllib.request.urlopen", return_value=MockResp()):
        res = check_bazos_search_rank(
            portal_item_id="223514742",
            title="VW Arteon SB",
            subdomain="auto.bazos.cz",
            max_pages=2
        )

        assert res["found"] is True
        assert res["rank_position"] == 2
        assert res["rank_page"] == 1
        assert res["is_top"] is True
        assert res["total_results"] == 15
        assert res["query"] == "VW Arteon SB"


def test_check_bazos_search_rank_not_found():
    mock_html = """
    <html>
        <body>
            <div class="inzeratynadpis">Zobrazeno 1-20 inzerátů z 150</div>
            <div class="inzeraty inzeratyflex">
                <div class="nadpis"><a href="/inzerat/999999/jiny.htm">Jiný inzerát</a></div>
            </div>
        </body>
    </html>
    """.encode("utf-8")

    class MockResp:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def read(self):
            return mock_html

    with patch("urllib.request.urlopen", return_value=MockResp()):
        res = check_bazos_search_rank(
            portal_item_id="223514742",
            title="VW Arteon",
            subdomain="auto.bazos.cz",
            max_pages=2
        )

        assert res["found"] is False
        assert res["rank_position"] is None
        assert res["rank_page"] is None
        assert res["total_results"] == 150


def test_db_rank_persistence():
    # Vytvoříme testovací záznam v DB
    listing_id = "test-rank-ad-1"
    ad = {
        "id": listing_id,
        "title": "Testovací inzerát",
        "description": "Popis",
        "price": 1000,
        "category": "auto",
        "condition": "Aktivní",
        "local_photos_dir": "test_dir",
        "target_bazos": 1
    }
    portal_states = {
        "bazos": {
            "portal_item_id": "12345678",
            "url": "https://auto.bazos.cz/inzerat/12345678/test.htm",
            "status": "Aktivní",
            "views": 50
        }
    }
    save_listing(ad, portal_states)

    rank_data = {
        "rank_position": 14,
        "rank_page": 1,
        "total_results": 45,
        "query": "Testovací inzerát",
        "checked_at": "2026-09-25T21:00:00"
    }

    updated = update_listing_portal_rank(listing_id, "bazos", rank_data)
    assert updated is True

    loaded = get_listing_by_id(listing_id)
    assert loaded is not None
    assert loaded.get("search_rank") == 14
    assert loaded.get("search_rank_page") == 1
    assert loaded.get("search_rank_total") == 45
    assert loaded.get("search_query") == "Testovací inzerát"
    assert loaded.get("search_rank_checked_at") == "2026-09-25T21:00:00"


def test_api_sms_top_info_endpoint():
    from app import app
    client = app.test_client()

    listing_id = "test-sms-top-ad"
    ad = {
        "id": listing_id,
        "title": "VW Golf VII",
        "price": 250000,
        "category": "auto",
        "local_photos_dir": "golf_photos",
        "target_bazos": 1
    }
    save_listing(ad, {
        "bazos": {
            "portal_item_id": "87654321",
            "url": "https://auto.bazos.cz/inzerat/87654321/golf.htm",
            "status": "Aktivní"
        }
    })

    resp = client.get(f"/api/listings/{listing_id}/sms_top_info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["portal_item_id"] == "87654321"
    assert data["phone_number"] == "90333"
    assert data["sms_body"] == "BAZOS 87654321"
    assert "sms:90333?body=BAZOS%2087654321" in data["sms_uri"]
    assert data["qr_content"] == "SMSTO:90333:BAZOS 87654321"
    assert data["price_czk"] == 79
