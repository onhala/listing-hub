"""
tests.unit.test_sauto_portal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit testy pro integraci portálu Sauto.cz (SautoPortal, URL parser,
detekce expirace a Expiration Sentinel endpoint).
"""

import io
import urllib.error
import pytest
from unittest.mock import patch, MagicMock

from listing_hub.portals.sauto.sauto_portal import SautoPortal
from listing_hub.portals.registry import portal_registry
import listing_hub.core.db as db
from app import app as flask_app


@pytest.fixture
def client(mock_db):
    flask_app.testing = True
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def sauto_portal():
    return SautoPortal()


def test_sauto_portal_properties(sauto_portal):
    assert sauto_portal.name == "sauto"
    assert sauto_portal.display_name == "Sauto.cz"
    assert "sauto.cz" in sauto_portal.supported_domains
    assert "www.sauto.cz" in sauto_portal.supported_domains
    assert sauto_portal.validate_url("https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491") is True
    assert sauto_portal.validate_url("https://sauto.cz/detail/1234567") is True
    assert sauto_portal.validate_url("https://bazos.cz/inzerat/123.php") is False


def test_sauto_extract_item_id(sauto_portal):
    assert sauto_portal.extract_item_id_from_url("https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491") == "20658491"
    assert sauto_portal.extract_item_id_from_url("https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491?utm_source=seznam") == "20658491"
    assert sauto_portal.extract_item_id_from_url("https://sauto.cz/detail/1234567") == "1234567"
    assert sauto_portal.extract_item_id_from_url("https://www.sauto.cz/inzerat/987654321/") == "987654321"
    assert sauto_portal.extract_item_id_from_url("") is None
    assert sauto_portal.extract_item_id_from_url(None) is None
    assert sauto_portal.extract_item_id_from_url("https://sauto.cz/kontakt") is None


def test_sauto_fetch_ad_details_active(sauto_portal):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Volkswagen Arteon Shooting Brake R-Line - Sauto.cz</title>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Vehicle",
            "name": "Volkswagen Arteon Shooting Brake 2.0 TSI",
            "offers": {
                "@type": "Offer",
                "price": 799000,
                "priceCurrency": "CZK"
            }
        }
        </script>
    </head>
    <body>
        <h1>Volkswagen Arteon Shooting Brake R-Line</h1>
        <span class="price">799 000 Kč</span>
        <div data-v-test="views">"viewsCount": 1420</div>
    </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = html_content.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        details = sauto_portal.fetch_ad_details("https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491")
        assert details["status"] == "Aktivní"
        assert details["is_active"] is True
        assert details["price"] == 799000
        assert details["views"] == 1420
        assert "Arteon" in details["title"]


def test_sauto_fetch_ad_details_expired_text(sauto_portal):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Sauto.cz</title></head>
    <body>
        <div class="message-box">
            <h2>Tento inzerát již není aktivní</h2>
            <p>Platnost inzerátu vypršela nebo byl inzerát smazán uživatelem.</p>
        </div>
    </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = html_content.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        details = sauto_portal.fetch_ad_details("https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491")
        assert details["status"] == "Expirováno"
        assert details["is_active"] is False


def test_sauto_fetch_ad_details_http_404(sauto_portal):
    err = urllib.error.HTTPError("https://www.sauto.cz/detail/123", 404, "Not Found", {}, None)
    with patch("urllib.request.urlopen", side_effect=err):
        details = sauto_portal.fetch_ad_details("https://www.sauto.cz/detail/123")
        assert details["status"] == "Expirováno"
        assert details["is_active"] is False


def test_sauto_registry_detection():
    portal = portal_registry.get_portal("sauto")
    assert portal is not None
    assert portal.name == "sauto"

    detected = portal_registry.detect_portal_from_url("https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491")
    assert detected is not None
    assert detected.name == "sauto"


def test_sauto_api_status_refresh_endpoint(client):
    # Vytvoříme inzerát v DB
    listing_id = "test-arteon-123"
    db.save_listing({
        "id": listing_id,
        "title": "VW Arteon SB R-Line 2.0 TSI",
        "price": 799000,
        "status": "Aktivní",
        "description": "Top stav",
        "category": "Auto"
    })
    db.record_manual_publication(listing_id, "sauto", portal_label="Sauto.cz", url="https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491")

    html_content = """
    <html>
    <head><title>VW Arteon - Sauto.cz</title></head>
    <body>
        <span>"viewsCount": 1550</span>
        <span>799000 Kč</span>
    </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = html_content.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = client.post(f"/api/listings/{listing_id}/portal-status-refresh", json={"portal_name": "sauto"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert data["portal_status"] == "Aktivní"
        assert data["is_active"] is True
        assert data["views"] == 1550

        # Ověříme, že se zapsalo do DB
        updated_l = db.get_listing_by_id(listing_id)
        sauto_st = updated_l["portal_states"]["sauto"]
        assert sauto_st["status"] == "Aktivní"
        assert sauto_st["views"] == 1550
