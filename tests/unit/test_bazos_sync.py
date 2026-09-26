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


def test_scrape_listings_from_html_modern_structure():
    """
    Ověří, že scraper bezpečně parsuje moderní HTML strukturu Bazoše s inzeratynadpis
    a h2.nadpis a odfiltruje odkaz na náhledovou fotku.
    """
    from listing_hub.portals.bazos.scraper import scrape_listings_from_html

    sample_html = """
    <div class="inzeraty inzeratyflex">
        <div class="inzeratynadpis">
            <a href="/inzerat/223514742/vw-arteon.php"><img class="obrazek" src="thumb.jpg"></a>
            <h2 class="nadpis"><a href="/inzerat/223514742/vw-arteon.php">VW Arteon SB R-Line 2.0 TSI</a></h2>
            <span class="velikost10">- <span class="ztop" title="TOP 1x Platí do 20.9. 2026">TOP</span> - [18.9. 2026]</span>
        </div>
        <div class="inzeratycena"><b>799 000 Kč</b></div>
        <div class="inzeratyview">509 x</div>
    </div>
    """
    ads = scrape_listings_from_html(sample_html)
    assert len(ads) == 1
    assert ads[0]["title"] == "VW Arteon SB R-Line 2.0 TSI"
    assert ads[0]["price"] == 799000
    assert ads[0]["views"] == 509
    assert ads[0]["is_top"] is True
    assert ads[0]["top_expires_at"] == "2026-09-20"


def test_post_to_bazos_edit_price_uses_smazat_endpoint():
    """
    Ověří, že akce editace ceny a mazání v post_to_bazos směřují na /smazat/{id}.php
    namísto odstraněného /delete.php.
    """
    import post_to_bazos

    mock_page = MagicMock()
    mock_page.content.return_value = "<html><body></body></html>"
    mock_page.url = "https://auto.bazos.cz/smazat/223514742.php"
    
    # Locators
    mock_loc = MagicMock()
    mock_loc.count.return_value = 1
    mock_loc.first = mock_loc
    mock_loc.is_visible.return_value = True
    mock_page.locator.return_value = mock_loc

    ad = {
        "title": "VW Arteon",
        "price": 799000,
        "url": "https://auto.bazos.cz/inzerat/223514742/vw-arteon.php",
        "local_photos_dir": ""
    }
    user_config = {
        "email": "test@example.com",
        "phone": "775123456",
        "bazos_password": "testpassword"
    }

    with patch("listing_hub.portals.bazos.session.session_manager.get_session", return_value=(None, None, None, mock_page)), \
         patch("listing_hub.portals.bazos.session.session_manager.wait_while", return_value=True):
        
        success = post_to_bazos._run_playwright_action_impl(
            ad=ad,
            user_config=user_config,
            action="edit_price",
            extra_val="799000",
            is_web=True
        )

        assert success is True
        # Ověříme, že navigace šla na /smazat/223514742.php a ne na /delete.php
        goto_urls = [call.args[0] for call in mock_page.goto.call_args_list]
        assert any("/smazat/223514742.php" in url for url in goto_urls)
        assert not any("/delete.php" in url for url in goto_urls)


def test_bazos_sync_checks_and_stores_search_rank(mock_db):
    """
    Ověří, že během synchronizace z Bazoše se automaticky ověří živá pozice (search rank)
    inzerátu a uloží do SQLite.
    """
    portal = BazosPortal()

    # Existující inzerát v DB
    local_ad = {
        "id": "ad_rank_sync_1",
        "title": "VW Arteon Shooting Brake 2.0 TSI",
        "description": "Krásný stav",
        "price": 750000,
        "category": "auto.bazos.cz",
        "condition": "Aktivní",
        "local_photos_dir": "photos/arteon",
        "location": "Praha",
        "notes": "",
        "ad_password_b64": "MTIzNDU2",
        "bookmarklet_uri": "",
        "days_old": 5,
        "created_at": "2026-09-20",
        "target_bazos": 1,
        "target_aukro": 0
    }
    portal_states = {
        "bazos": {
            "portal_item_id": "223514742",
            "url": "https://auto.bazos.cz/inzerat/223514742/vw-arteon.php",
            "status": "Aktivní",
            "views": 150,
            "last_synced": "2026-09-21T10:00:00"
        }
    }
    save_listing(local_ad, portal_states)

    scraped_mock = [
        {
            "title": "VW Arteon Shooting Brake 2.0 TSI",
            "price": 750000,
            "views": 180,
            "url": "https://auto.bazos.cz/inzerat/223514742/vw-arteon.php",
            "date_created": "2026-09-20"
        }
    ]

    mock_rank_data = {
        "found": True,
        "rank_position": 3,
        "rank_page": 1,
        "query": "VW Arteon Shooting",
        "is_top": True,
        "total_results": 45,
        "checked_at": "2026-09-26T12:00:00"
    }

    mock_page = MagicMock()
    mock_page.locator.return_value.is_visible.return_value = False
    mock_page.content.return_value = "<html></html>"

    with patch("listing_hub.portals.bazos.session.session_manager.run_on_worker", side_effect=lambda func, *args, **kwargs: func(mock_page, *args, **kwargs)), \
         patch("listing_hub.portals.bazos.session.session_manager.get_session", return_value=(None, None, None, mock_page)), \
         patch("listing_hub.portals.bazos.bazos_portal.scrape_listings_from_html", return_value=scraped_mock), \
         patch("listing_hub.portals.bazos.bazos_portal.fetch_bazos_ad_details", return_value={"description": "Krásný stav", "location": "Praha", "is_top": True, "top_expires_at": "2026-09-30", "top_info": "TOP 1x"}), \
         patch("listing_hub.portals.bazos.bazos_portal.check_bazos_search_rank", return_value=mock_rank_data):

        result = portal.sync_listings({"email": "test@example.com", "phone": "777123456"})

        assert len(result) == 1
        assert result[0]["search_rank"] == 3
        assert result[0]["search_rank_page"] == 1
        assert result[0]["search_query"] == "VW Arteon Shooting"
        assert result[0]["is_top"] is True

        # Ověříme uložení v DB
        listings = get_all_listings()
        assert len(listings) == 1
        ad_db = listings[0]
        assert ad_db["search_rank"] == 3
        assert ad_db["search_rank_page"] == 1
        assert ad_db["search_query"] == "VW Arteon Shooting"
        assert ad_db["is_top"] is True


def test_sms_top_info_endpoint_returns_accurate_details(mock_db):
    """
    Ověří, že endpoint /api/listings/<listing_id>/sms_top_info vrací správný formát SMS
    a QR kód i při různých formátech zadání ID.
    """
    from app import app

    local_ad = {
        "id": "ad_sms_top_test",
        "title": "Škoda Superb III Combi",
        "description": "Top stav",
        "price": 420000,
        "category": "auto.bazos.cz",
        "condition": "Aktivní",
        "local_photos_dir": "photos/superb",
        "location": "České Budějovice",
        "notes": "",
        "ad_password_b64": "MTIzNDU2",
        "bookmarklet_uri": "",
        "days_old": 10,
        "created_at": "2026-09-15",
        "target_bazos": 1,
        "target_aukro": 0
    }
    portal_states = {
        "bazos": {
            "portal_item_id": "199887766",
            "url": "https://auto.bazos.cz/inzerat/199887766/skoda-superb.php",
            "status": "Aktivní",
            "views": 320,
            "last_synced": "2026-09-25T10:00:00"
        }
    }
    save_listing(local_ad, portal_states)

    client = app.test_client()

    # 1. Dotaz podle UUID inzerátu
    resp = client.get("/api/listings/ad_sms_top_test/sms_top_info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["portal_item_id"] == "199887766"
    assert data["phone_number"] == "90333"
    assert data["sms_body"] == "BAZOS 199887766"
    assert "sms:90333" in data["sms_uri"]
    assert "SMSTO:90333:BAZOS 199887766" == data["qr_content"]
    assert data["title"] == "Škoda Superb III Combi"

    # 2. Dotaz přímo podle čísla inzerátu (čistý číselný identifikátor)
    resp_numeric = client.get("/api/listings/199887766/sms_top_info")
    assert resp_numeric.status_code == 200
    data_num = resp_numeric.get_json()
    assert data_num["status"] == "success"
    assert data_num["portal_item_id"] == "199887766"




