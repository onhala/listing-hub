import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime
from listing_hub.portals.bazos.bazos_portal import BazosPortal
from listing_hub.core.db import get_all_listings, save_listing

def test_bazos_sync_auto_imports_missing_listings(mock_db):
    """
    Ověří, že synchronizace inzerátů automaticky importuje chybějící inzeráty z Bazoše do SQLite.
    """
    portal = BazosPortal()
    
    # 1. Připravíme mockovaná scraped data z Bazoše (obsahuje 1 nový externí inzerát)
    scraped_mock = [
        {
            "title": "Novy externi inzerat",
            "price": 999,
            "views": 42,
            "url": "https://dum.bazos.cz/inzerat/987654321/novy-externi-inzerat.php",
            "date_created": datetime.today().strftime("%Y-%m-%d")
        }
    ]
    
    user_config = {
        "email": "test@example.com",
        "phone": "777654321",
        "location": "Praha 1"
    }
    
    # Mockujeme Playwright session a scrape_listings_from_html z post_to_bazos
    mock_page = MagicMock()
    mock_page.locator.return_value.is_visible.return_value = False
    mock_page.content.return_value = "<html></html>"
    
    with patch("listing_hub.portals.bazos.session.session_manager.run_on_worker", side_effect=lambda func, *args, **kwargs: func(mock_page, *args, **kwargs)), \
         patch("listing_hub.portals.bazos.session.session_manager.get_session", return_value=(None, None, None, mock_page)), \
         patch("listing_hub.portals.bazos.bazos_portal.scrape_listings_from_html", return_value=scraped_mock):
        
        # Spustíme synchronizaci
        result = portal.sync_listings(user_config)
        
        # Ověříme návratovou hodnotu
        assert len(result) == 1
        assert result[0]["title"] == "Novy externi inzerat"
        assert result[0]["portal_item_id"] == "987654321"
        
        # Ověříme, že nový inzerát byl zapsán do SQLite
        listings = get_all_listings()
        assert len(listings) == 1
        
        ad = listings[0]
        assert ad["title"] == "Novy externi inzerat"
        assert ad["price"] == 999
        assert ad["target_bazos"] == 1
        assert ad["target_aukro"] == 0
        
        # Ověříme stav portálu
        bazos_state = ad["portal_states"]["bazos"]
        assert bazos_state["portal_item_id"] == "987654321"
        assert bazos_state["status"] == "Aktivní"
        assert bazos_state["views"] == 42
