import pytest
from listing_hub.core.db import save_listing, get_all_listings, delete_listing

def test_crud_operations():
    # 1. Verify initially empty
    initial_listings = get_all_listings()
    assert len(initial_listings) == 0

    # 2. Save a listing
    listing_data = {
        "id": "item123",
        "title": "Zahradní stůl",
        "description": "Dřevěný stůl na zahradu",
        "price": 1500,
        "category": "nabytek",
        "condition": "Použité",
        "local_photos_dir": "photos/item123",
        "location": "Praha",
        "notes": "Spěchá",
        "ad_password_b64": "MTIzNDU2",
        "bookmarklet_uri": "javascript:...",
        "days_old": 2,
        "created_at": "2026-07-15",
        "target_bazos": 1,
        "target_aukro": 0
    }
    
    portal_states = {
        "bazos": {
            "portal_item_id": "bazos_id_456",
            "url": "https://nabytek.bazos.cz/inzerat/bazos_id_456",
            "status": "Aktivní",
            "views": 42,
            "last_synced": "2026-07-15T12:00:00"
        }
    }
    
    save_listing(listing_data, portal_states)

    # 3. Retrieve and verify
    listings = get_all_listings()
    assert len(listings) == 1
    retrieved = listings[0]
    assert retrieved["id"] == "item123"
    assert retrieved["title"] == "Zahradní stůl"
    assert retrieved["price"] == 1500
    assert "bazos" in retrieved["portal_states"]
    assert retrieved["portal_states"]["bazos"]["portal_item_id"] == "bazos_id_456"
    assert retrieved["portal_states"]["bazos"]["views"] == 42

    # 4. Update the listing
    listing_data["price"] = 1200
    portal_states["bazos"]["views"] = 50
    save_listing(listing_data, portal_states)
    
    listings = get_all_listings()
    assert len(listings) == 1
    assert listings[0]["price"] == 1200
    assert listings[0]["portal_states"]["bazos"]["views"] == 50

    # 5. Delete the listing
    delete_listing("item123")
    assert len(get_all_listings()) == 0
