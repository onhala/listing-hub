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


def test_bazos_sync_skips_historical_publications(mock_db):
    """
    Ověří, že synchronizace inzerátů ignoruje staré inzeráty z Bazoše, které již
    byly archivovány v listing_publications (ochrana proti Zombie Resurrection).
    """
    from listing_hub.core.db import record_publication, close_active_publication

    portal = BazosPortal()

    # 1. Existující inzerát v Listing Hubu
    listing_data = {
        "id": "sekacka_1",
        "title": "Sekačka",
        "description": "Benzínová sekačka",
        "price": 4500,
        "category": "dum",
        "condition": "Použité",
        "local_photos_dir": "photos/sekacka_1",
        "location": "Praha",
        "notes": "",
        "ad_password_b64": "MTIzNDU2",
        "bookmarklet_uri": "",
        "days_old": 1,
        "created_at": "2026-08-01",
        "target_bazos": 1,
        "target_aukro": 0
    }
    portal_states = {
        "bazos": {
            "portal_item_id": "222000111",
            "url": "https://dum.bazos.cz/inzerat/222000111/sekacka.php",
            "status": "Aktivní",
            "views": 3,
            "last_synced": "2026-08-02T10:00:00"
        }
    }
    save_listing(listing_data, portal_states)

    # V historii máme staré vystavení s ID "111000222"
    record_publication(
        listing_id="sekacka_1",
        portal_name="bazos",
        portal_item_id="111000222",
        url="https://dum.bazos.cz/inzerat/111000222/sekacka-puvodni.php",
        price=5000,
        status="superseded"
    )

    # 2. Bazoš vrátí při scrapingu oba inzeráty (nový i starý, pokud se ještě nestihl promazat)
    scraped_mock = [
        {
            "title": "Sekačka",
            "price": 4500,
            "views": 5,
            "url": "https://dum.bazos.cz/inzerat/222000111/sekacka.php",
            "date_created": datetime.today().strftime("%Y-%m-%d")
        },
        {
            "title": "Sekačka původní",
            "price": 5000,
            "views": 40,
            "url": "https://dum.bazos.cz/inzerat/111000222/sekacka-puvodni.php",
            "date_created": "2026-08-01"
        }
    ]

    user_config = {
        "email": "test@example.com",
        "phone": "777654321",
        "location": "Praha"
    }

    mock_page = MagicMock()
    mock_page.locator.return_value.is_visible.return_value = False
    mock_page.content.return_value = "<html></html>"

    with patch("listing_hub.portals.bazos.session.session_manager.run_on_worker", side_effect=lambda func, *args, **kwargs: func(mock_page, *args, **kwargs)), \
         patch("listing_hub.portals.bazos.session.session_manager.get_session", return_value=(None, None, None, mock_page)), \
         patch("listing_hub.portals.bazos.bazos_portal.scrape_listings_from_html", return_value=scraped_mock):

        result = portal.sync_listings(user_config)

        # 3. Ověření: V Listing Hubu musí stále existovat pouze 1 listing (sekacka_1), starý inzerát nesmí být importován jako duplicita!
        listings = get_all_listings()
        assert len(listings) == 1
        assert listings[0]["id"] == "sekacka_1"
        assert listings[0]["portal_states"]["bazos"]["portal_item_id"] == "222000111"
        assert listings[0]["portal_states"]["bazos"]["views"] == 5


def test_fetch_bazos_ad_details_extracts_popisdetail_not_similar_popis():
    """
    Ověří, že fetch_bazos_ad_details extrahuje skutečný popis z div.popisdetail
    a lokaci z hlavní tabulky inzerátu a nesahá do sekce 'Podobné inzeráty' (div.popis, span.inzeratylok).
    """
    from listing_hub.portals.bazos.bazos_portal import fetch_bazos_ad_details
    import io

    sample_html = """
    <html>
    <head><title>Bazoš detail</title></head>
    <body>
        <h1>Elektrická strunová sekačka AL-KO TE 600</h1>
        <table class="listadv">
            <tr>
                <td>Lokalita:</td>
                <td>381 01 Český Krumlov</td>
            </tr>
            <tr>
                <td>Cena:</td>
                <td><b>400 Kč</b></td>
            </tr>
        </table>
        <div class="popisdetail">
            Prodám plně funkční elektrickou strunovou sekačku AL-KO TE 600.
            Lehká, zachovalá, motor 600W.
        </div>

        <div class="podobne">
            <h2>Podobné inzeráty</h2>
            <div class="inzeraty">
                <span class="nadpis"><a href="#">Black & Decker GL360</a></span>
                <div class="popis">Úplně cizí popis sekačky Black & Decker ze spodku stránky.</div>
                <span class="inzeratylok">Praha 1</span>
                <span class="cena">350 Kč</span>
            </div>
        </div>
    </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.geturl.return_value = "https://dum.bazos.cz/inzerat/223744456/strunovka.php"
    mock_resp.read.return_value = sample_html.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        details = fetch_bazos_ad_details("https://dum.bazos.cz/inzerat/223744456/strunovka.php")

    assert details["is_deleted"] is False
    assert details["title"] == "Elektrická strunová sekačka AL-KO TE 600"
    assert "Prodám plně funkční elektrickou strunovou sekačku AL-KO TE 600" in details["description"]
    assert "Black & Decker" not in details["description"]
    assert "381 01 Český Krumlov" in details["location"]
    assert details["price"] == 400


def test_bazos_sync_keyword_matching_for_reposted_ads(mock_db):
    """
    Ověří, že znovuvystavený inzerát s mírně pozměněným titulkem se spáruje
    podle shody klíčových slov (Priority 4) a nevytvoří nový duplicitní listing.
    """
    portal = BazosPortal()

    # 1. Lokální inzerát s původním názvem
    listing_data = {
        "id": "plamenak_1",
        "title": "Obří nafukovací ostrov XXL Plameňák pro 5 osob",
        "description": "Původní popis ostrova",
        "price": 3900,
        "category": "ostatni",
        "condition": "Použité",
        "local_photos_dir": "photos/plamenak_1",
        "location": "České Budějovice",
        "notes": "",
        "ad_password_b64": "MTIzNDU2",
        "bookmarklet_uri": "",
        "days_old": 10,
        "created_at": "2026-08-01",
        "target_bazos": 1,
        "target_aukro": 0
    }
    portal_states = {
        "bazos": {
            "portal_item_id": "222999000",
            "url": "https://sport.bazos.cz/inzerat/222999000/stary-plamenak.php",
            "status": "Aktivní",
            "views": 25,
            "last_synced": "2026-08-05T10:00:00"
        }
    }
    save_listing(listing_data, portal_states)

    # 2. Bazoš vrátí nový inzerát s pozměněným titulkem
    scraped_mock = [
        {
            "title": "XXL Plameňák ostrov pro 5 osob - TOP stav",
            "price": 3900,
            "views": 1,
            "url": "https://sport.bazos.cz/inzerat/223745085/xxl-plamenak-ostrov.php",
            "date_created": datetime.today().strftime("%Y-%m-%d")
        }
    ]

    user_config = {
        "email": "test@example.com",
        "phone": "777654321",
        "location": "České Budějovice"
    }

    mock_page = MagicMock()
    mock_page.locator.return_value.is_visible.return_value = False
    mock_page.content.return_value = "<html></html>"

    mock_detail = {
        "description": "Nový reálný popis ostrova Plameňák z Bazoše.",
        "location": "370 01 České Budějovice",
        "title": "XXL Plameňák ostrov pro 5 osob - TOP stav",
        "price": 3900,
        "is_deleted": False
    }

    with patch("listing_hub.portals.bazos.session.session_manager.run_on_worker", side_effect=lambda func, *args, **kwargs: func(mock_page, *args, **kwargs)), \
         patch("listing_hub.portals.bazos.session.session_manager.get_session", return_value=(None, None, None, mock_page)), \
         patch("listing_hub.portals.bazos.bazos_portal.scrape_listings_from_html", return_value=scraped_mock), \
         patch("listing_hub.portals.bazos.bazos_portal.fetch_bazos_ad_details", return_value=mock_detail):

        portal.sync_listings(user_config)

        # 3. Ověříme, že nevznikla duplicita a původní záznam byl aktualizován
        listings = get_all_listings()
        assert len(listings) == 1
        assert listings[0]["id"] == "plamenak_1"
        assert listings[0]["title"] == "XXL Plameňák ostrov pro 5 osob - TOP stav"
        assert listings[0]["portal_states"]["bazos"]["portal_item_id"] == "223745085"
        assert listings[0]["description"] == "Nový reálný popis ostrova Plameňák z Bazoše."


