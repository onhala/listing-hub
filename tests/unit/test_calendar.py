import pytest
from datetime import date, timedelta
from listing_hub.core.calendar import generate_ical_feed, escape_ical_text, parse_listing_created_date

def test_escape_ical_text():
    raw = "Text with, comma; and newline\nand backslash\\"
    escaped = escape_ical_text(raw)
    assert "\\," in escaped
    assert "\\;" in escaped
    assert "\\n" in escaped
    assert "\\\\" in escaped

def test_parse_listing_created_date():
    listing_iso = {"created_at": "2026-06-15T10:00:00"}
    assert parse_listing_created_date(listing_iso) == date(2026, 6, 15)

    listing_cz = {"created_at": "15.06.2026"}
    assert parse_listing_created_date(listing_cz) == date(2026, 6, 15)

    listing_days = {"days_old": 5}
    expected = date.today() - timedelta(days=5)
    assert parse_listing_created_date(listing_days) == expected

def test_generate_ical_feed_active_and_sold():
    listings = [
        {
            "id": "ad-1",
            "title": "Aku vrtačka DeWalt",
            "price": 2500,
            "status": "Aktivní",
            "created_at": "2026-08-01",
            "portal_states": {
                "bazos": {
                    "url": "https://dum.bazos.cz/inzerat/12345/dewalt.php",
                    "status": "Aktivní"
                }
            }
        },
        {
            "id": "ad-2",
            "title": "Kávovar DeLonghi",
            "price": 4000,
            "status": "Prodané",
            "created_at": "2026-07-01",
            "portal_states": {
                "bazos": {
                    "url": "https://elektro.bazos.cz/inzerat/999/delonghi.php",
                    "status": "Prodané"
                }
            }
        },
        {
            "id": "ad-3",
            "title": "Smazaný inzerát",
            "status": "Smazáno",
            "created_at": "2026-06-01"
        }
    ]

    feed = generate_ical_feed(listings, base_hub_url="http://192.168.1.50:5001")
    
    # RFC 5545 basic structure
    assert feed.startswith("BEGIN:VCALENDAR")
    assert feed.endswith("END:VCALENDAR\r\n")
    assert "PRODID:-//Listing Hub//Bazos Calendar Feed//CS" in feed

    # Active listing checks
    assert "UID:listinghub-ad-1@roboton.com" in feed
    assert "SUMMARY:⚠️ Vyprší inzerát: Aku vrtačka DeWalt (2 500 Kč)" in feed
    assert "BEGIN:VALARM" in feed
    assert "TRIGGER:-P3D" in feed
    assert "TRIGGER:-PT0M" in feed
    assert "https://dum.bazos.cz/inzerat/12345/dewalt.php" in feed
    assert "http://192.168.1.50:5001/#tab-active" in feed

    # Sold listing checks
    assert "UID:listinghub-ad-2@roboton.com" in feed
    assert "SUMMARY:✅ PRODÁNO: Kávovar DeLonghi (4 000 Kč)" in feed
    assert "http://192.168.1.50:5001/#tab-sold" in feed

    # Deleted listing should NOT be in feed
    assert "ad-3" not in feed
    assert "Smazaný inzerát" not in feed
