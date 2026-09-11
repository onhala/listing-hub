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


def test_listing_publications_crud_and_stats():
    from listing_hub.core.db import (
        record_publication,
        close_active_publication,
        get_listing_publications,
        get_publication_by_url_or_item_id,
        get_listing_cumulative_stats,
        get_listing_by_id
    )

    # 1. Setup listing
    listing_data = {
        "id": "pub_item_1",
        "title": "Sekačka",
        "description": "Benzínová sekačka",
        "price": 5000,
        "category": "dum",
        "condition": "Použité",
        "local_photos_dir": "photos/pub_item_1",
        "location": "Praha",
        "notes": "",
        "ad_password_b64": "MTIzNDU2",
        "bookmarklet_uri": "",
        "days_old": 0,
        "created_at": "2026-08-01",
        "target_bazos": 1,
        "target_aukro": 0
    }
    save_listing(listing_data, {})

    # 2. Record first publication
    pub1_id = record_publication(
        listing_id="pub_item_1",
        portal_name="bazos",
        portal_item_id="111222333",
        url="https://dum.bazos.cz/inzerat/111222333/sekacka.php",
        price=5000,
        status="active"
    )
    assert pub1_id > 0

    pubs = get_listing_publications("pub_item_1")
    assert len(pubs) == 1
    assert pubs[0]["portal_item_id"] == "111222333"
    assert pubs[0]["status"] == "active"
    assert pubs[0]["price"] == 5000

    # 3. Lookup by URL or item_id
    found_by_id = get_publication_by_url_or_item_id(portal_name="bazos", portal_item_id="111222333")
    assert found_by_id is not None
    assert found_by_id["listing_id"] == "pub_item_1"

    found_by_url = get_publication_by_url_or_item_id(portal_name="bazos", url="https://dum.bazos.cz/inzerat/111222333/sekacka.php")
    assert found_by_url is not None
    assert found_by_url["id"] == pub1_id

    # 4. Close first publication (reposted/superseded) and record second publication
    close_active_publication(listing_id="pub_item_1", portal_name="bazos", close_reason="reposted", final_views=25)

    pub2_id = record_publication(
        listing_id="pub_item_1",
        portal_name="bazos",
        portal_item_id="444555666",
        url="https://dum.bazos.cz/inzerat/444555666/sekacka-sleva.php",
        price=4500,
        status="active"
    )
    assert pub2_id > pub1_id

    # 5. Verify publications list order (oldest first as per db ORDER BY id ASC)
    pubs = get_listing_publications("pub_item_1")
    assert len(pubs) == 2
    assert pubs[0]["portal_item_id"] == "111222333"
    assert pubs[0]["status"] == "superseded"
    assert pubs[0]["views"] == 25
    assert pubs[1]["portal_item_id"] == "444555666"
    assert pubs[1]["status"] == "active"

    # 6. Cumulative stats
    stats = get_listing_cumulative_stats("pub_item_1")
    assert stats["publication_count"] == 2
    assert stats["total_views"] == 25  # 25 + 0
    assert stats["is_reposted"] is True

    # 7. Verify enriched get_listing_by_id
    item = get_listing_by_id("pub_item_1")
    assert item["publication_count"] == 2
    assert item["cumulative_views"] == 25
    assert item["is_reposted"] is True
    assert len(item["publications"]) == 2

    # 8. Deletion cascades to publications
    delete_listing("pub_item_1")
    assert len(get_listing_publications("pub_item_1")) == 0

