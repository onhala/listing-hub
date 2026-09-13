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


def test_mark_listing_as_sold_comprehensive():
    from listing_hub.core.db import (
        save_listing,
        get_listing_by_id,
        record_publication,
        get_listing_publications,
        mark_listing_as_sold,
    )

    # 1. Setup listing with active portal state and publication
    listing_data = {
        "id": "sold_item_1",
        "title": "Kolo Author",
        "price": 5000,
        "category": "sport",
        "condition": "Použité",
        "local_photos_dir": "photos/sold_item_1",
    }
    portal_states = {
        "bazos": {
            "portal_item_id": "999888",
            "url": "https://sport.bazos.cz/inzerat/999888/kolo.php",
            "status": "Aktivní",
            "views": 15,
        }
    }
    save_listing(listing_data, portal_states)

    pub_id = record_publication(
        listing_id="sold_item_1",
        portal_name="bazos",
        portal_item_id="999888",
        url="https://sport.bazos.cz/inzerat/999888/kolo.php",
        price=5000,
        status="active"
    )

    # 2. Mark as sold
    success = mark_listing_as_sold(
        listing_id="sold_item_1",
        sale_price=4500,
        sold_at="2026-09-12",
        notes="Sleva 500 Kč při rychlém jednání"
    )
    assert success is True

    # 3. Verify listing attributes
    item = get_listing_by_id("sold_item_1")
    assert item["sale_price"] == 4500
    assert item["sold_at"] == "2026-09-12"
    assert item["sold_notes"] == "Sleva 500 Kč při rychlém jednání"

    # 4. Verify portal_states status changed to 'Prodané'
    assert item["portal_states"]["bazos"]["status"] == "Prodané"

    # 5. Verify publication is closed with status 'sold'
    pubs = get_listing_publications("sold_item_1")
    assert len(pubs) == 1
    assert pubs[0]["status"] == "sold"
    assert pubs[0]["closed_at"] == "2026-09-12"
    assert pubs[0]["close_reason"] == "sold"

    # 6. Edge case: Non-existent ID returns False
    res_non_existent = mark_listing_as_sold("non_existent_id", 1000)
    assert res_non_existent is False

    # 7. Price casting & fallback
    save_listing({"id": "sold_item_cast", "title": "Casting test", "price": 1200}, {})
    mark_listing_as_sold("sold_item_cast", sale_price="1500.50")
    item_cast = get_listing_by_id("sold_item_cast")
    assert item_cast["sale_price"] == 1500
    assert item_cast["portal_states"]["bazos"]["status"] == "Prodané"

    mark_listing_as_sold("sold_item_cast", sale_price="invalid")
    item_cast2 = get_listing_by_id("sold_item_cast")
    assert item_cast2["sale_price"] == 1200  # fallback na původní cenu


def test_restore_sold_listing_comprehensive():
    from listing_hub.core.db import (
        save_listing,
        get_listing_by_id,
        mark_listing_as_sold,
        restore_sold_listing,
    )

    # 1. Setup sold listing
    listing_data = {
        "id": "restore_item_1",
        "title": "Vrtačka Bosch",
        "price": 2500,
    }
    portal_states = {
        "bazos": {
            "status": "Aktivní",
            "url": "https://dum.bazos.cz/inzerat/123",
        }
    }
    save_listing(listing_data, portal_states)
    mark_listing_as_sold("restore_item_1", sale_price=2200, sold_at="2026-09-11", notes="Osobka")

    # Verify sold state
    sold_item = get_listing_by_id("restore_item_1")
    assert sold_item["sale_price"] == 2200
    assert sold_item["sold_at"] == "2026-09-11"
    assert sold_item["sold_notes"] == "Osobka"
    assert sold_item["portal_states"]["bazos"]["status"] == "Prodané"

    # 2. Restore sold listing
    success = restore_sold_listing("restore_item_1")
    assert success is True

    # 3. Verify cleaned attributes and status changed to 'Expirováno'
    restored_item = get_listing_by_id("restore_item_1")
    assert restored_item["sale_price"] is None
    assert restored_item["sold_at"] is None
    assert restored_item["sold_notes"] is None
    assert restored_item["portal_states"]["bazos"]["status"] == "Expirováno"

    # 4. Edge case: Non-existent ID returns False
    assert restore_sold_listing("non_existent_restore_id") is False


def test_get_sold_statistics_comprehensive():
    from listing_hub.core.db import (
        save_listing,
        mark_listing_as_sold,
        restore_sold_listing,
        get_sold_statistics,
        delete_listing,
        get_all_listings,
    )

    # 1. Empty database stats
    for l in get_all_listings():
        delete_listing(l["id"])

    empty_stats = get_sold_statistics()
    assert empty_stats == {
        "total_sold": 0,
        "total_profit": 0,
        "avg_price": 0
    }

    # 2. Add active (unsold) listings - stats should remain zero
    save_listing({"id": "active_1", "title": "Stůl", "price": 1000}, {"bazos": {"status": "Aktivní"}})
    save_listing({"id": "active_2", "title": "Židle", "price": 500}, {"bazos": {"status": "Aktivní"}})
    active_stats = get_sold_statistics()
    assert active_stats == {
        "total_sold": 0,
        "total_profit": 0,
        "avg_price": 0
    }

    # 3. Mark items as sold
    mark_listing_as_sold("active_1", sale_price=900)
    mark_listing_as_sold("active_2", sale_price=400)

    # Add a third sold listing with multi-portal state (bazos + aukro both 'Prodané')
    # to verify deduplication
    save_listing(
        {"id": "multi_portal_sold", "title": "Lampa", "price": 2000},
        {
            "bazos": {"status": "Prodané"},
            "aukro": {"status": "Prodané"}
        }
    )
    mark_listing_as_sold("multi_portal_sold", sale_price=1700)

    stats = get_sold_statistics()
    # Total sold should be 3 (not 4, despite 2 portal states for multi_portal_sold)
    assert stats["total_sold"] == 3
    # Total profit: 900 + 400 + 1700 = 3000 (multi_portal_sold is NOT counted twice!)
    assert stats["total_profit"] == 3000
    # Average price: 3000 / 3 = 1000
    assert stats["avg_price"] == 1000

    # 4. Restore one item and verify stats recalculation
    restore_sold_listing("active_2")
    stats_after_restore = get_sold_statistics()
    assert stats_after_restore["total_sold"] == 2
    assert stats_after_restore["total_profit"] == 2600  # 900 + 1700
    assert stats_after_restore["avg_price"] == 1300     # 2600 / 2


