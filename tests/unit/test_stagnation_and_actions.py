"""
tests.unit.test_stagnation_and_actions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit testy pro funkce v3.14.0 a v3.15.0:
- SMS Top Helper endpoint
- Search Rank Tracker endpoint
- Multi-portal views refresh & manual URL binding
- Stagnation & Rotten listing indicators
"""

import pytest
from unittest.mock import patch, MagicMock
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


def test_sms_top_info_endpoint_success(client, mock_db):
    listing_id = "test-sms-top-1"
    listing_data = {
        "id": listing_id,
        "title": "VW Arteon SB R-Line",
        "price": 799000,
        "category": "Auto",
        "created_at": "2026-09-01"
    }
    portal_states = {
        "bazos": {
            "portal_name": "bazos",
            "url": "https://auto.bazos.cz/inzerat/223514742/vw-arteon.php",
            "portal_item_id": "223514742",
            "status": "Aktivní",
            "views": 500
        }
    }
    mock_db.save_listing(listing_data, portal_states)

    response = client.get(f"/api/listings/{listing_id}/sms_top_info")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["portal_item_id"] == "223514742"
    assert data["sms_text"] == "TOP 223514742"
    assert data["sms_phone"] == "90200"
    assert "auto.bazos.cz" in data["url"]


def test_sms_top_info_endpoint_missing_listing(client, mock_db):
    response = client.get("/api/listings/nonexistent-id/sms_top_info")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"


def test_sms_top_info_endpoint_no_bazos_ad(client, mock_db):
    listing_id = "test-no-bazos"
    listing_data = {
        "id": listing_id,
        "title": "Stůl",
        "price": 1000
    }
    mock_db.save_listing(listing_data, {})

    response = client.get(f"/api/listings/{listing_id}/sms_top_info")
    assert response.status_code == 400
    data = response.get_json()
    assert "není vystaven na Bazoši" in data["message"]


def test_check_rank_endpoint_success(client, mock_db):
    listing_id = "test-rank-1"
    listing_data = {
        "id": listing_id,
        "title": "Škoda Octavia Combi",
        "price": 250000
    }
    portal_states = {
        "bazos": {
            "portal_name": "bazos",
            "url": "https://auto.bazos.cz/inzerat/1998877/octavia.php",
            "portal_item_id": "1998877",
            "status": "Aktivní"
        }
    }
    mock_db.save_listing(listing_data, portal_states)

    mock_rank_result = {
        "found": True,
        "rank_position": 3,
        "rank_page": 1,
        "query": "Škoda Octavia",
        "is_top": True,
        "total_results": 140,
        "checked_at": "2026-09-25T20:00:00"
    }

    with patch("listing_hub.portals.bazos.rank_tracker.check_bazos_search_rank", return_value=mock_rank_result):
        response = client.post(f"/api/listings/{listing_id}/check_rank", json={"query": "Škoda Octavia"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert data["rank"]["found"] is True
        assert data["rank"]["rank_position"] == 3
        assert data["rank"]["rank_page"] == 1


def test_portal_views_refresh_with_registry(client, mock_db):
    listing_id = "test-views-refresh"
    listing_data = {
        "id": listing_id,
        "title": "Bunda Nike",
        "price": 800
    }
    portal_states = {
        "sbazar": {
            "portal_name": "sbazar",
            "url": "https://www.sbazar.cz/inzerat/18923412-bunda-nike",
            "status": "Aktivní",
            "views": 10
        }
    }
    mock_db.save_listing(listing_data, portal_states)

    with patch("listing_hub.portals.registry.portal_registry.scrape_views_for_portal", return_value=85):
        response = client.post(f"/api/listings/{listing_id}/portal-views-refresh", json={"portal_name": "sbazar"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert data["views"] == 85

        # Ověříme, že DB byla aktualizována
        updated = mock_db.get_listing_by_id(listing_id)
        assert updated["portal_states"]["sbazar"]["views"] == 85


def test_update_portal_url_endpoint(client, mock_db):
    listing_id = "test-portal-url"
    listing_data = {
        "id": listing_id,
        "title": "Kolo Trek",
        "price": 15000
    }
    mock_db.save_listing(listing_data, {})

    response = client.post(f"/api/listings/{listing_id}/portal-url", json={
        "portal_name": "vinted",
        "url": "https://www.vinted.cz/items/45920192-kolo-trek"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"

    updated = mock_db.get_listing_by_id(listing_id)
    assert "vinted" in updated["portal_states"]
    assert updated["portal_states"]["vinted"]["url"] == "https://www.vinted.cz/items/45920192-kolo-trek"
