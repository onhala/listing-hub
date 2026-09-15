import pytest
from listing_hub.core import db
from listing_hub.core.db import save_listing, record_views_snapshot
from listing_hub.metrics.exporter import generate_prometheus_metrics, sanitize_label_value, parse_iso_to_unix
from app import app

def test_sanitize_label_value():
    assert sanitize_label_value('Test "Quotes" & \n Newline') == 'Test \\"Quotes\\" &   Newline'
    assert sanitize_label_value(None) == ""
    long_str = "A" * 100
    sanitized = sanitize_label_value(long_str)
    assert len(sanitized) <= 60
    assert sanitized.endswith("...")

def test_parse_iso_to_unix():
    ts = parse_iso_to_unix("2026-07-15T12:00:00")
    assert ts > 0
    assert parse_iso_to_unix("") == 0.0
    assert parse_iso_to_unix("invalid") == 0.0

def test_generate_prometheus_metrics_empty():
    metrics = generate_prometheus_metrics()
    assert "listinghub_up 1" in metrics
    assert "listinghub_listings_count{status=\"active\"} 0" in metrics
    assert "listinghub_listings_count{status=\"sold\"} 0" in metrics
    assert "listinghub_active_inventory_value_czk 0" in metrics
    assert "listinghub_listing_views_total 0" in metrics

def test_generate_prometheus_metrics_with_data():
    # 1. Uložíme aktivní inzerát na Bazoši
    listing_active = {
        "id": "ad-active-1",
        "title": "Aku vrtačka Bosch",
        "description": "Profesionální vrtačka",
        "price": 2500,
        "category": "naradi",
        "condition": "Použité",
        "days_old": 5,
        "created_at": "2026-09-10"
    }
    portal_states_active = {
        "bazos": {
            "portal_item_id": "111222",
            "url": "https://dum.bazos.cz/inzerat/111222",
            "status": "Aktivní",
            "views": 45,
            "is_top": 1,
            "last_synced": "2026-09-15T10:00:00"
        }
    }
    save_listing(listing_active, portal_states_active)

    # 2. Uložíme prodaný inzerát s kanálem FB
    listing_sold = {
        "id": "ad-sold-1",
        "title": "Monitor Dell 27",
        "description": "IPS panel",
        "price": 4000,
        "sale_price": 3500,
        "sold_at": "2026-09-14",
        "sold_channel": "facebook",
        "category": "pc",
        "condition": "Použité",
        "days_old": 12,
        "created_at": "2026-09-02"
    }
    portal_states_sold = {
        "facebook": {
            "portal_item_id": "fb999",
            "url": "https://facebook.com/marketplace/item/fb999",
            "status": "Prodané",
            "views": 120,
            "is_top": 0,
            "last_synced": "2026-09-14T18:00:00"
        }
    }
    save_listing(listing_sold, portal_states_sold)

    # 3. Zaznamenáme snapshot zhlédnutí do historie
    record_views_snapshot("ad-active-1", "bazos", 45)

    # Ověříme záznam v listing_views_history
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listing_views_history WHERE listing_id = 'ad-active-1'")
    assert cursor.fetchone()[0] == 1
    conn.close()

    # 4. Vygenerujeme metriky
    metrics = generate_prometheus_metrics()

    # Ověření výstupů
    assert "listinghub_up 1" in metrics
    assert "listinghub_listings_count{status=\"active\"} 1" in metrics
    assert "listinghub_listings_count{status=\"sold\"} 1" in metrics
    assert "listinghub_active_inventory_value_czk 2500" in metrics
    assert "listinghub_listing_views_total 45" in metrics
    assert 'listinghub_listing_views{id="ad-active-1",title="Aku vrtačka Bosch",portal="bazos",category="naradi"} 45' in metrics
    assert 'listinghub_listing_price_czk{id="ad-active-1",title="Aku vrtačka Bosch",portal="bazos"} 2500' in metrics
    assert 'listinghub_listing_is_top{id="ad-active-1",title="Aku vrtačka Bosch",portal="bazos"} 1' in metrics
    assert 'listinghub_portal_listings_count{portal="bazos"} 1' in metrics
    assert 'listinghub_portal_views_total{portal="bazos"} 45' in metrics
    assert "listinghub_sales_total_czk 3500" in metrics
    assert "listinghub_sales_count_total 1" in metrics
    assert 'listinghub_sales_by_channel_total_czk{channel="facebook"} 3500' in metrics
    assert 'listinghub_listing_days_to_expire{id="ad-active-1",title="Aku vrtačka Bosch",portal="bazos"} 55' in metrics
    assert 'listinghub_listing_photos_count{id="ad-active-1",title="Aku vrtačka Bosch",portal="bazos"} 0' in metrics
    assert "listinghub_sales_avg_days_to_sell 12.0" in metrics
    assert 'listinghub_sales_days_to_sell{id="ad-sold-1",title="Monitor Dell 27",channel="facebook"} 12' in metrics

def test_flask_metrics_endpoint():
    client = app.test_client()
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.content_type
    assert "version=0.0.4" in response.content_type
    assert b"listinghub_up 1" in response.data
