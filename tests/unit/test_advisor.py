import pytest
from unittest.mock import MagicMock, patch
from listing_hub.ai.advisor import get_price_recommendation, clean_price

def test_clean_price():
    assert clean_price("3 500 Kč") == 3500
    assert clean_price("12000") == 12000
    assert clean_price("Dohodou") is None
    assert clean_price("") is None

def test_get_price_recommendation_overpriced(mock_db):
    """Ověří doporučení snížení ceny při předraženém inzerátu."""
    # Vytvoříme testovací inzerát s cenou 5000 Kč v mock_db
    from listing_hub.core.db import save_listing
    listing_id = "test-ad-uuid"
    save_listing({
        "id": listing_id,
        "title": "Sekacka Hecht",
        "price": 5000,
        "category": "Zahrada"
    })
    
    # Mockujeme analýzu trhu z Bazoše, která vrátí medián 3500 Kč
    analysis_mock = {
        "query": "Sekacka Hecht",
        "total_found": 3,
        "prices_count": 3,
        "statistics": {
            "min": 2000,
            "max": 4000,
            "avg": 3100,
            "median": 3500,
            "suggested_quick_sale": 3150,
            "suggested_fair": 3500,
            "suggested_premium": 3850
        },
        "listings": [
            {"title": "Sekacka 1", "price": 2000, "price_text": "2000 Kč", "link": "http://..", "location": "Brno", "views": "1", "is_top": False},
            {"title": "Sekacka 2", "price": 3500, "price_text": "3500 Kč", "link": "http://..", "location": "Praha", "views": "2", "is_top": False},
            {"title": "Sekacka 3", "price": 4000, "price_text": "4000 Kč", "link": "http://..", "location": "Plzen", "views": "3", "is_top": False}
        ]
    }
    
    with patch("listing_hub.ai.advisor.analyze_bazos_prices", return_value=analysis_mock):
        res = get_price_recommendation(listing_id)
        assert "error" not in res, f"Chyba v testu: {res.get('error')}"
        assert res["status"] == "OVERPRICED"
        # 5000 je o 43% více než medián 3500
        assert res["diff_percent"] == 43
        assert "vyšší než tržní medián" in res["message"]
        assert res["statistics"]["median"] == 3500

def test_get_price_recommendation_bargain(mock_db):
    """Ověří, že inzerát s nižší cenou je označen jako výhodný."""
    from listing_hub.core.db import save_listing
    listing_id = "test-ad-uuid-2"
    save_listing({
        "id": listing_id,
        "title": "Kolo Author",
        "price": 2000,
        "category": "Sport"
    })
    
    analysis_mock = {
        "query": "Kolo Author",
        "total_found": 1,
        "prices_count": 1,
        "statistics": {
            "min": 3000,
            "max": 3000,
            "avg": 3000,
            "median": 3000,
            "suggested_quick_sale": 2700,
            "suggested_fair": 3000,
            "suggested_premium": 3300
        },
        "listings": [
            {"title": "Kolo 1", "price": 3000, "price_text": "3000 Kč", "link": "http://..", "location": "Praha", "views": "5", "is_top": False}
        ]
    }
    
    with patch("listing_hub.ai.advisor.analyze_bazos_prices", return_value=analysis_mock):
        res = get_price_recommendation(listing_id)
        
        assert res["status"] == "BARGAIN"
        # 2000 je o 33% méně než medián 3000
        assert res["diff_percent"] == -33
        assert "výhodná" in res["message"]
