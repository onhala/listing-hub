import os
import io
import zipfile
import json
import tempfile
import pytest
from unittest.mock import patch
from PIL import Image

from listing_hub.core import db
from app import app, strip_exif_and_normalize


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_listing(tmp_path):
    # Ensure fresh DB state for this test item
    listing_id = "test-manual-pub-item-1"
    db.save_listing({
        "id": listing_id,
        "title": "Zahradní gril Weber",
        "description": "Kvalitní gril v perfektním stavu.",
        "price": 3500,
        "category": "Dům a zahrada",
        "local_photos_dir": str(tmp_path)
    })
    yield listing_id
    db.delete_listing(listing_id)


def test_db_record_manual_publication(sample_listing):
    """Testuje uložení ruční publikace na externím portálu."""
    success = db.record_manual_publication(
        listing_id=sample_listing,
        portal_name="facebook",
        portal_label="FB Marketplace",
        url="https://www.facebook.com/marketplace/item/123456",
        notes="Sdíleno do lokální skupiny"
    )
    assert success is True

    listing = db.get_listing_by_id(sample_listing)
    assert listing is not None
    assert "facebook" in listing["portal_states"]
    fb_state = listing["portal_states"]["facebook"]
    assert fb_state["status"] == "Aktivní"
    assert fb_state["portal_label"] == "FB Marketplace"
    assert fb_state["url"] == "https://www.facebook.com/marketplace/item/123456"
    assert "Sdíleno do lokální skupiny" in listing["notes"]


def test_db_update_listing_portal_url(sample_listing):
    """Testuje doplnění a aktualizaci URL odkazu pro daný portál."""
    db.record_manual_publication(
        listing_id=sample_listing,
        portal_name="sbazar",
        portal_label="Sbazar.cz",
        url=""
    )

    success = db.update_listing_portal_url(
        listing_id=sample_listing,
        portal_name="sbazar",
        url="https://www.sbazar.cz/inzerat/987654"
    )
    assert success is True

    listing = db.get_listing_by_id(sample_listing)
    assert listing["portal_states"]["sbazar"]["url"] == "https://www.sbazar.cz/inzerat/987654"


def test_api_publish_manual(client, sample_listing):
    """Testuje REST API endpoint /api/listings/<id>/publish-manual."""
    res = client.post(f"/api/listings/{sample_listing}/publish-manual", json={
        "portal_name": "vinted",
        "portal_label": "Vinted",
        "url": "https://www.vinted.cz/items/456",
        "notes": "Přidáno na Vinted"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"

    listing = db.get_listing_by_id(sample_listing)
    assert "vinted" in listing["portal_states"]
    assert listing["portal_states"]["vinted"]["url"] == "https://www.vinted.cz/items/456"


def test_api_portal_url(client, sample_listing):
    """Testuje REST API endpoint /api/listings/<id>/portal-url."""
    db.record_manual_publication(sample_listing, "aukro", "Aukro.cz", "")
    res = client.post(f"/api/listings/{sample_listing}/portal-url", json={
        "portal_name": "aukro",
        "url": "https://aukro.cz/polozka-111"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"

    listing = db.get_listing_by_id(sample_listing)
    assert listing["portal_states"]["aukro"]["url"] == "https://aukro.cz/polozka-111"


def test_api_photos_zip_download(client, tmp_path):
    """Testuje stažení fotografií ve formátu ZIP archívu."""
    listing_id = "test-zip-item"
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()

    # Vytvoření testovacích obrázků
    img1 = Image.new("RGB", (60, 60), color="blue")
    img1.save(photo_dir / "foto1.jpg")
    img2 = Image.new("RGB", (60, 60), color="red")
    img2.save(photo_dir / "foto2.png")

    db.save_listing({
        "id": listing_id,
        "title": "Předmět s fotkami",
        "local_photos_dir": str(photo_dir)
    })

    try:
        res = client.get(f"/api/photos/{listing_id}/zip")
        assert res.status_code == 200
        assert res.headers["Content-Type"] == "application/zip"
        assert "attachment" in res.headers.get("Content-Disposition", "")

        # Ověření integrity ZIP archívu
        with zipfile.ZipFile(io.BytesIO(res.data), "r") as zf:
            file_names = zf.namelist()
            assert any("foto1.jpg" in name for name in file_names)
            assert any("foto2.png" in name for name in file_names)
    finally:
        db.delete_listing(listing_id)


def test_mark_sold_with_sold_channel(client, sample_listing):
    """Testuje zaznamenání prodejního kanálu při označení inzerátu za prodaný."""
    res = client.post(f"/api/listings/{sample_listing}/mark_sold", json={
        "sale_price": 3200,
        "sold_at": "2026-09-13",
        "notes": "Prodáno na FB Marketplace",
        "sold_channel": "facebook",
        "delete_on_bazos": False
    })
    assert res.status_code == 200

    listing = db.get_listing_by_id(sample_listing)
    assert listing["sold_channel"] == "facebook"
    assert listing["sale_price"] == 3200

    # Ověříme, že statistika s kanály obsahuje prodej na facebooku
    stats = db.get_sold_statistics(include_channels=True)
    assert "by_channel" in stats
    assert "facebook" in stats["by_channel"]
    assert stats["by_channel"]["facebook"]["count"] >= 1


def test_strip_exif_and_normalize(tmp_path):
    """Testuje bezpečné odstranění EXIF metadat z nahrané fotografie."""
    img_path = tmp_path / "test_exif.jpg"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(img_path)

    # Spustíme normalizaci a odstranění EXIF
    result = strip_exif_and_normalize(str(img_path))
    assert result is True

    # Znovu otevřeme a ověříme formát a velikost
    with Image.open(img_path) as verified_img:
        assert verified_img.size == (100, 100)
        # EXIF by měl být None nebo prázdný
        exif = verified_img.getexif()
        assert len(exif) == 0


def test_api_sms_relay(client):
    """Testuje endpoint pro automatické předávání SMS ověřovacího kódu z telefonu."""
    # 1. Standardní SMS zpráva od Bazoše
    res = client.post("/api/sms/relay", json={
        "text": "Vas overovaci kod pro Bazos je: 839214. Platnost 10 minut."
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] in ("ok", "warning")
    assert data["code"] == "839214"

    # 2. Přímý parametr 'code'
    res2 = client.post("/api/sms/relay", json={
        "code": "1234"
    })
    assert res2.status_code == 200
    assert res2.get_json()["code"] == "1234"
