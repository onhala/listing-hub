"""
Unit tests for batch operations, Bazos rubriky recommendation engine,
rubriky endpoints, and sold statistics under edge and extreme conditions.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import app
from app import app as flask_app, count_photos
from listing_hub.portals.bazos.categories import (
    BAZOS_ALL_SUBDOMAINS,
    DOMAIN_KEYWORDS,
    rank_target_domains,
    get_target_domain,
    normalize_cz,
    extract_subdomain,
    extract_ad_id,
    match_best_category_option,
)
import listing_hub.core.db as db
from listing_hub.agent.api import safe_resolve_photos_dir


@pytest.fixture
def client():
    """Flask test client fixture."""
    flask_app.testing = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def clean_listings():
    """Ensure database has no listings before and after test."""
    conn = db.get_db_connection()
    try:
        conn.execute("DELETE FROM listing_publications")
        conn.execute("DELETE FROM portal_states")
        conn.execute("DELETE FROM listings")
        conn.commit()
    finally:
        conn.close()

    yield

    conn = db.get_db_connection()
    try:
        conn.execute("DELETE FROM listing_publications")
        conn.execute("DELETE FROM portal_states")
        conn.execute("DELETE FROM listings")
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# 1. Bazos Rubrika Recommendation Edge Cases (rank_target_domains & helpers)
# ============================================================================

def test_rank_target_domains_abbreviations_and_tech_terms():
    """Ověří doporučování rubrik pro odborné zkratky a specifickou terminologii."""
    # PC / Hardware
    res_pc = rank_target_domains("Herní PC RTX 4080, AMD Ryzen 7, 32GB RAM, 2TB SSD")
    assert res_pc[0]["domain"] == "pc.bazos.cz"
    matched_pc = res_pc[0]["matched_keywords"]
    assert any(k in matched_pc for k in ["rtx", "ryzen", "ram", "ssd", "pocitac"])

    # Auto / Automotive
    res_auto = rank_target_domains("Škoda Superb 2.0 TDI 140kW DSG 4x4 Combi")
    assert res_auto[0]["domain"] == "auto.bazos.cz"
    assert "skoda" in res_auto[0]["matched_keywords"] or "tdi" in res_auto[0]["matched_keywords"]

    # Stroje a technika / Průmysl
    res_stroje = rank_target_domains("Vysokozdvižný vozík VZV Desta s hydraulikou")
    assert res_stroje[0]["domain"] == "stroje.bazos.cz"
    assert any(k in res_stroje[0]["matched_keywords"] for k in ["vzv", "desta", "hydraulick", "vysokozdviz"])

    # Mobily a chytré hodinky
    res_mobil = rank_target_domains("Chytré hodinky Apple Watch Ultra 2 smartwatch")
    assert res_mobil[0]["domain"] == "mobil.bazos.cz"
    assert any(k in res_mobil[0]["matched_keywords"] for k in ["smartwatch", "apple watch", "mobil"])

    # Sport / E-bike
    res_sport = rank_target_domains("Horský ebike s baterií Bosch 625Wh")
    assert res_sport[0]["domain"] == "sport.bazos.cz"
    assert any(k in res_sport[0]["matched_keywords"] for k in ["ebike", "kolo"])

    # Práce / Úvazky
    res_prace = rank_target_domains("Přijmeme řidiče sk. C - HPP / DPP, mzda 55.000 Kč")
    assert res_prace[0]["domain"] == "prace.bazos.cz"
    assert any(k in res_prace[0]["matched_keywords"] for k in ["hpp", "dpp", "mzda", "prace"])

    # Elektro / Spotřebiče
    res_elektro = rank_target_domains("LG OLED Smart TV 55 palců 4K")
    assert res_elektro[0]["domain"] == "elektro.bazos.cz"
    assert any(k in res_elektro[0]["matched_keywords"] for k in ["tv", "televiz"])


def test_rank_target_domains_diacritics_and_casing():
    """Ověří robustnost vůči verzálkám (CAPS), české diakritice a speciálním znakům."""
    # Všechna velká písmena s diakritikou
    res_caps = rank_target_domains("DĚTSKÝ KOČÁREK CYBEX PRIAM SE SPORTOVNÍ KORBOU")
    assert res_caps[0]["domain"] == "deti.bazos.cz"
    assert res_caps[0]["score"] > 0

    # Malá písmena s háčky a čárkami
    res_lower = rank_target_domains("výkonný drtič větví / štěpkovač atika")
    assert res_lower[0]["domain"] == "dum.bazos.cz"
    assert any(k in res_lower[0]["matched_keywords"] for k in ["drtic", "stepkov"])

    # Punctuation and symbols
    res_punct = rank_target_domains("--- [[ DÁMSKÉ ŠATY A SUKNĚ ]] --- (velikost M)!!!")
    assert res_punct[0]["domain"] == "obleceni.bazos.cz"
    assert any(k in res_punct[0]["matched_keywords"] for k in ["saty", "sukne"])

    # Test samotné pomocné funkce normalize_cz
    assert normalize_cz("Příliš Žluťoučký Kůň Úpěl Ďábelské Ódy") == "prilis zlutoucky kun upel dabelske ody"
    assert normalize_cz("Cena: 1.500,- Kč (sleva možná!)") == "cena 1 500 kc sleva mozna"
    assert normalize_cz("") == ""
    assert normalize_cz(None) == ""
    assert normalize_cz("   ") == ""
    assert normalize_cz(12345) == "12345"


def test_rank_target_domains_ambiguous_and_multicategory_matches():
    """Ověří chování u víceznačných slov (např. dětské horské kolo, motobunda vs bunda)."""
    # 1. "Dětské horské kolo" -> shoda jak v deti, tak ve sport
    ranked = rank_target_domains("Dětské horské kolo AUTHOR 24")
    top_domains = [r["domain"] for r in ranked[:2]]
    assert "deti.bazos.cz" in top_domains
    assert "sport.bazos.cz" in top_domains

    deti_item = next(r for r in ranked if r["domain"] == "deti.bazos.cz")
    sport_item = next(r for r in ranked if r["domain"] == "sport.bazos.cz")
    assert deti_item["score"] > 0
    assert sport_item["score"] > 0
    assert any("detsk" in k for k in deti_item["matched_keywords"])
    assert any("kolo" in k for k in sport_item["matched_keywords"])

    # Pokud uživatel specifikuje kategorii "sport", sport musí získat vyšší skóre
    ranked_sport = rank_target_domains("Dětské horské kolo AUTHOR 24", category="sport")
    assert ranked_sport[0]["domain"] == "sport.bazos.cz"

    # Pokud uživatel specifikuje kategorii "deti", deti musí získat vyšší skóre
    ranked_deti = rank_target_domains("Dětské horské kolo AUTHOR 24", category="deti")
    assert ranked_deti[0]["domain"] == "deti.bazos.cz"

    # 2. Motocyklová bunda vs běžná bunda:
    # "Motocyklová bunda" má získat bonus pro motorky
    ranked_moto = rank_target_domains("Motocyklová bunda Revit s chrániči")
    assert ranked_moto[0]["domain"] == "motorky.bazos.cz"

    # "Pánská zimní bunda" nesmí spadnout do motorek
    ranked_bunda = rank_target_domains("Pánská zimní péřová bunda The North Face")
    assert ranked_bunda[0]["domain"] == "obleceni.bazos.cz"
    moto_score = next(r["score"] for r in ranked_bunda if r["domain"] == "motorky.bazos.cz")
    assert moto_score == 0

    # 3. "Elektromotor" nesmí falešně sepnout motorky kvůli slovu "moto"
    ranked_elmotor = rank_target_domains("Třífázový elektromotor 4 kW 1450 ot/min na cirkulárku")
    moto_entry = next(r for r in ranked_elmotor if r["domain"] == "motorky.bazos.cz")
    assert moto_entry["score"] == 0

    # 4. "Zahradní stůl a židle" -> shoda v dům i nábytek
    ranked_stul = rank_target_domains("Zahradní dřevěný stůl a 4 židle")
    dum_score = next(r["score"] for r in ranked_stul if r["domain"] == "dum.bazos.cz")
    nabytek_score = next(r["score"] for r in ranked_stul if r["domain"] == "nabytek.bazos.cz")
    assert dum_score > 0
    assert nabytek_score > 0


def test_rank_target_domains_unrecognized_items_and_fallback():
    """Ověří fallback chování při nerozpoznaných předmětech nebo prázdných vstupech."""
    # 1. Zcela neznámý předmět bez klíčových slov
    unknown_ranked = rank_target_domains("Xyzaqwerty 99999 unikátní artefakt")
    assert len(unknown_ranked) == 20
    assert all(r["score"] == 0 for r in unknown_ranked)
    assert all(len(r["matched_keywords"]) == 0 for r in unknown_ranked)

    # get_target_domain musí vrátit fallback dum.bazos.cz
    assert get_target_domain("Xyzaqwerty 99999 unikátní artefakt") == "dum.bazos.cz"

    # 2. Prázdný název, None, nebo pouze speciální znaky
    assert get_target_domain("") == "dum.bazos.cz"
    assert get_target_domain(None) == "dum.bazos.cz"
    assert get_target_domain("   ") == "dum.bazos.cz"
    assert get_target_domain("!@#$%^&*()_+") == "dum.bazos.cz"

    # 3. Nerozpoznaný název, ale klíčové slovo v popisu
    desc_ranked = rank_target_domains("Předmět z pozůstalosti", description="Prodám plně funkční pračku a lednici")
    assert desc_ranked[0]["domain"] == "elektro.bazos.cz"
    assert get_target_domain("Předmět z pozůstalosti", description="Prodám plně funkční pračku a lednici") == "elektro.bazos.cz"

    # 4. Nerozpoznaný název, ale shoda v kategorii
    cat_ranked = rank_target_domains("Neznámá věc 123", category="Nábytek do předsíně")
    assert cat_ranked[0]["domain"] == "nabytek.bazos.cz"
    assert get_target_domain("Neznámá věc 123", category="Nábytek do předsíně") == "nabytek.bazos.cz"


def test_rank_target_domains_nonstandard_urls():
    """Ověří parsování subdomén a ID inzerátů při nestandardních formátech URL."""
    # Standardní platná URL
    url_standard = "https://auto.bazos.cz/inzerat/189999999/skoda-octavia.php"
    res_url = rank_target_domains("Libovolný název", original_url=url_standard)
    assert res_url[0]["domain"] == "auto.bazos.cz"
    assert res_url[0]["score"] >= 1000

    # URL s query parametry a kotvou (hash)
    url_query = "https://hudba.bazos.cz/inzerat/777888/kytara.php?source=search&page=2#detail"
    res_query = rank_target_domains("Předmět", original_url=url_query)
    assert res_query[0]["domain"] == "hudba.bazos.cz"
    assert res_query[0]["score"] >= 1000

    # URL bez subdomény (např. www.bazos.cz) - nesmí získat 1000 bodů, určí se podle textu
    url_www = "https://www.bazos.cz/inzerat/12345/sekacka.php"
    res_www = rank_target_domains("Benzínová sekačka na trávu", original_url=url_www)
    assert res_www[0]["domain"] == "dum.bazos.cz"
    assert res_www[0]["score"] < 1000

    # Neplatné URL a jiné protokoly
    assert extract_subdomain("http://stroje.bazos.cz/inzerat/123") == "dum.bazos.cz"  # http regex fallback
    assert extract_subdomain("ftp://dum.bazos.cz/test") == "dum.bazos.cz"
    assert extract_subdomain("neplatna_adresa_bez_protokolu") == "dum.bazos.cz"
    assert extract_subdomain("") == "dum.bazos.cz"
    assert extract_subdomain(None) == "dum.bazos.cz"

    # extract_ad_id hraniční případy
    assert extract_ad_id("https://dum.bazos.cz/inzerat/123456789/sekacka.php") == "123456789"
    assert extract_ad_id("/inzerat/42") == "42"
    assert extract_ad_id("https://dum.bazos.cz/inzerat/neplatne-id/test.php") is None
    assert extract_ad_id("https://bazos.cz/rubrika/dum/") is None
    assert extract_ad_id("") is None
    assert extract_ad_id(None) is None


def test_match_best_category_option_edge_cases():
    """Ověří hraniční případy párování možností kategorií ve formuláři Bazoše."""
    # Prázdné možnosti
    assert match_best_category_option([], "Název") == (None, "", -1)

    # Možnosti s neplatnými hodnotami ('', '0')
    dummy_options = [("", "Vyberte kategorii"), ("0", "Zvolte")]
    assert match_best_category_option(dummy_options, "Sekačka")[0] is None

    # Fallback na 'ostatni' pokud není shoda
    fallback_options = [
        ("10", "Stroje na kov"),
        ("20", "Stroje na dřevo"),
        ("99", "Ostatní stroje"),
    ]
    val, lbl, score = match_best_category_option(fallback_options, "Neidentifikovatelný předmět")
    assert val == "99"
    assert "Ostatní" in lbl

    # Shoda se synonymem (např. drtič -> technika)
    garden_options = [
        ("1", "Sekačky"),
        ("2", "Zahradní technika"),
        ("3", "Bazény"),
        ("4", "Ostatní"),
    ]
    val, lbl, score = match_best_category_option(garden_options, "Drtič zahradního odpadu")
    assert val == "2"
    assert lbl == "Zahradní technika"


# ============================================================================
# 2. Endpoint /api/bazos/rubriky Tests
# ============================================================================

def test_api_bazos_rubriky_complete_structure(client):
    """Ověří kompletní strukturu odpovědi endpointu /api/bazos/rubriky."""
    res = client.get("/api/bazos/rubriky")
    assert res.status_code == 200

    data = json.loads(res.data)
    assert data["status"] == "success"
    assert "rubriky" in data

    rubriky = data["rubriky"]
    assert isinstance(rubriky, list)
    assert len(rubriky) == 20, "Bazoš musí mít přesně 20 hlavních rubrik"

    # Ověříme unikátnost domén
    domains = [r.get("domain") for r in rubriky]
    assert len(set(domains)) == 20, "Všechny rubriky musí mít unikátní doménu"

    # Ověříme přítomnost všech klíčových subdomén
    expected_domains = {
        "deti.bazos.cz", "dum.bazos.cz", "nabytek.bazos.cz", "elektro.bazos.cz",
        "sport.bazos.cz", "auto.bazos.cz", "motorky.bazos.cz", "stroje.bazos.cz",
        "pc.bazos.cz", "mobil.bazos.cz", "foto.bazos.cz", "hudba.bazos.cz",
        "obleceni.bazos.cz", "knihy.bazos.cz", "zvirata.bazos.cz", "vstupenky.bazos.cz",
        "reality.bazos.cz", "prace.bazos.cz", "sluzby.bazos.cz", "ostatni.bazos.cz",
    }
    assert set(domains) == expected_domains

    # Ověříme formát ikon a labelů
    for item in rubriky:
        assert item["domain"].endswith(".bazos.cz")
        assert isinstance(item["label"], str) and len(item["label"].strip()) > 0
        assert isinstance(item["icon"], str)
        assert item["icon"].startswith("fa-"), f"Ikona {item['icon']} musí mít FontAwesome formát fa-*"


def test_api_bazos_rubriky_error_handling(client):
    """Ověří 500 error handling při chybě v serializaci nebo načtení rubrik."""
    real_jsonify = app.jsonify
    calls = 0

    def mock_jsonify(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Serializace selhala")
        return real_jsonify(*args, **kwargs)

    with patch("app.jsonify", side_effect=mock_jsonify):
        res = client.get("/api/bazos/rubriky")
        assert res.status_code == 500
        data = json.loads(res.data)
        assert data["status"] == "error"
        assert "Serializace selhala" in data["message"]


# ============================================================================
# 3. Endpoint /api/ai/suggest-rubrika Tests
# ============================================================================

def test_api_suggest_rubrika_empty_and_minimal_payload(client):
    """Ověří chování /api/ai/suggest-rubrika s prázdným nebo minimálním payloadem."""
    # 1. Prázdný JSON objekt
    res = client.post("/api/ai/suggest-rubrika", json={})
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert data["top_domain"] in ("deti.bazos.cz", "dum.bazos.cz")
    assert data["reason"] == "Výchozí doporučená rubrika"
    assert len(data["recommended"]) == 1
    assert len(data["all"]) == 20

    # 2. Prázdný řetězec v těle požadavku
    res_empty = client.post("/api/ai/suggest-rubrika", data="", content_type="application/json")
    assert res_empty.status_code == 200
    data_empty = json.loads(res_empty.data)
    assert data_empty["status"] == "success"
    assert data_empty["top_domain"] in ("deti.bazos.cz", "dum.bazos.cz")
    assert data_empty["reason"] == "Výchozí doporučená rubrika"


def test_api_suggest_rubrika_invalid_json_inputs(client):
    """Ověří, že neplatný JSON nezpůsobí 500 pád, ale vrátí graceful fallback."""
    res_malformed = client.post(
        "/api/ai/suggest-rubrika",
        data="INVALID_JSON_{missing: quotes, 123",
        content_type="application/json"
    )
    assert res_malformed.status_code == 200
    data = json.loads(res_malformed.data)
    assert data["status"] == "success"
    assert data["top_domain"] in ("deti.bazos.cz", "dum.bazos.cz")
    assert data["reason"] == "Výchozí doporučená rubrika"

    # Non-json Content-Type
    res_text = client.post(
        "/api/ai/suggest-rubrika",
        data="prostý text",
        content_type="text/plain"
    )
    assert res_text.status_code == 200
    data_text = json.loads(res_text.data)
    assert data_text["status"] == "success"
    assert data_text["top_domain"] in ("deti.bazos.cz", "dum.bazos.cz")


def test_api_suggest_rubrika_with_title_and_description(client):
    """Ověří doporučení rubriky na základě předaného názvu a popisu."""
    payload = {
        "title": "Pánské silniční kolo Trek Domane",
        "description": "Karbonový rám, komponenty Shimano 105, velmi lehký bicykl",
        "category": "sport"
    }
    res = client.post("/api/ai/suggest-rubrika", json=payload)
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert data["top_domain"] == "sport.bazos.cz"
    assert "Doporučeno na základě:" in data["reason"]
    assert any(k in data["reason"] for k in ["kolo", "sport", "horske"])


def test_api_suggest_rubrika_with_existing_listing_id(client, clean_listings):
    """Ověří vyhledání inzerátu v DB podle listing_id, když title není v payloadu."""
    listing_id = "test_suggest_db_item"
    db.save_listing({
        "id": listing_id,
        "title": "Dětská dřevěná postýlka s matrací",
        "description": "Kompletní výbavička pro miminko",
        "price": 1500,
        "local_photos_dir": "photos/postylka"
    }, portal_states={"bazos": {"url": ""}})

    res = client.post("/api/ai/suggest-rubrika", json={"listing_id": listing_id})
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert data["top_domain"] == "deti.bazos.cz"
    assert "Doporučeno na základě:" in data["reason"]


def test_api_suggest_rubrika_with_nonexistent_listing_id(client):
    """Ověří chování s neexistujícím listing_id."""
    res = client.post("/api/ai/suggest-rubrika", json={"listing_id": "nonexistent_guid_9999"})
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert data["top_domain"] in ("deti.bazos.cz", "dum.bazos.cz")
    assert data["reason"] == "Výchozí doporučená rubrika"


def test_api_suggest_rubrika_with_url_in_portal_states(client, clean_listings):
    """Ověří, že existující URL inzerátu v portal_states získá nejvyšší prioritu (+1000)."""
    listing_id = "test_url_override_item"
    db.save_listing({
        "id": listing_id,
        "title": "Univerzální držák",
        "description": "Kvalitní držák",
        "price": 500
    }, portal_states={
        "bazos": {
            "url": "https://motorky.bazos.cz/inzerat/111222/drzak-na-moto.php",
            "status": "Aktivní"
        }
    })

    res = client.post("/api/ai/suggest-rubrika", json={"listing_id": listing_id})
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["status"] == "success"
    assert data["top_domain"] == "motorky.bazos.cz"
    assert "původní adresa (motorky.bazos.cz)" in data["reason"]


def test_api_suggest_rubrika_exception_handling(client):
    """Ověří 500 error response při neočekávané výjimce v backendu."""
    with patch("listing_hub.portals.bazos.categories.rank_target_domains", side_effect=RuntimeError("Kategorizační selhání")):
        res = client.post("/api/ai/suggest-rubrika", json={"title": "Testovací inzerát"})
        assert res.status_code == 500
        data = json.loads(res.data)
        assert data["status"] == "error"
        assert "Kategorizační selhání" in data["message"]


# ============================================================================
# 4. Batch Operations & Backend Helper Functions
# ============================================================================

def test_batch_repost_validation_and_conflict(client, clean_listings):
    """Ověří validace parametrů a stav robota při dávkovém znovuvystavení."""
    # 1. Chybějící listing_id
    res_no_id = client.post("/api/action/repost_with_new_price", json={"new_price": 500})
    assert res_no_id.status_code == 400
    assert "Chybí listing_id nebo new_price" in json.loads(res_no_id.data)["message"]

    # 2. Chybějící new_price
    res_no_price = client.post("/api/action/repost_with_new_price", json={"listing_id": "item_1"})
    assert res_no_price.status_code == 400

    # 3. Neexistující listing_id
    res_not_found = client.post("/api/action/repost_with_new_price", json={"listing_id": "nonexistent", "new_price": 500})
    assert res_not_found.status_code == 404
    assert "Inzerát nebyl nalezen" in json.loads(res_not_found.data)["message"]

    # 4. Konflikt - robot je zaneprázdněn (409)
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True
    with patch("app.playwright_process", mock_thread):
        res_busy = client.post("/api/action/repost_with_new_price", json={"listing_id": "any", "new_price": 500})
        assert res_busy.status_code == 409
        assert "Jiná akce robota právě probíhá" in json.loads(res_busy.data)["message"]


def test_batch_repost_staging_does_not_mutate_db_prematurely(client, clean_listings):
    """Ověří, že spuštění akce znovuvystavení v dávce nezmění cenu v DB dříve než po potvrzení."""
    listing_id = "batch_stage_item"
    db.save_listing({
        "id": listing_id,
        "title": "Elektrická sekačka Hecht",
        "description": "Zánovní sekačka",
        "price": 3000,
        "local_photos_dir": "photos/sekacka",
        "ad_password_b64": "MTIzNA=="
    }, portal_states={"bazos": {"url": "https://dum.bazos.cz/inzerat/123", "portal_item_id": "123"}})

    with patch("threading.Thread.start") as mock_start:
        res = client.post("/api/action/repost_with_new_price", json={
            "listing_id": listing_id,
            "new_price": 2600,
            "target_domain": "dum.bazos.cz",
            "auto_delete_old": True
        })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "success"
        assert "2600 Kč" in data["message"]
        mock_start.assert_called_once()

    # DB cena musí zůstat 3000 Kč až do potvrzení akce!
    item = db.get_listing_by_id(listing_id)
    assert item["price"] == 3000


def test_batch_sequential_staging_and_confirm(client, clean_listings):
    """Simuluje sekvenční průchod 2 položek v dávce přes repost a confirm."""
    # Příprava 2 inzerátů
    db.save_listing({
        "id": "batch_item_1",
        "title": "Kolo 1",
        "price": 2000,
        "local_photos_dir": "photos/kolo1"
    }, portal_states={"bazos": {"url": "https://sport.bazos.cz/inzerat/111", "portal_item_id": "111"}})

    db.save_listing({
        "id": "batch_item_2",
        "title": "Kolo 2",
        "price": 4000,
        "local_photos_dir": "photos/kolo2"
    }, portal_states={"bazos": {"url": "https://sport.bazos.cz/inzerat/222", "portal_item_id": "222"}})

    # 1. Znovuvystavení položky 1
    with patch("threading.Thread.start"):
        res1 = client.post("/api/action/repost_with_new_price", json={
            "listing_id": "batch_item_1",
            "new_price": 1800,
            "target_domain": "sport.bazos.cz"
        })
        assert res1.status_code == 200

    # Potvrzení položky 1
    mock_status_1 = {
        "state": "ready_for_review",
        "action_type": "repost",
        "listing_id": "batch_item_1",
        "meta": {
            "staged_price": 1800,
            "old_portal_url": "https://sport.bazos.cz/inzerat/111",
            "old_portal_item_id": "111",
            "auto_delete_old": True
        }
    }
    worker_calls_1 = [
        {"still_on_form": False, "new_url": "https://sport.bazos.cz/inzerat/333/kolo-1-nove.php"},
        {"success": True, "status": "deleted", "reason": "Vymazán"}
    ]
    with patch("app.action_state_mgr.get_status", return_value=mock_status_1),          patch("app.session_manager.run_on_worker", side_effect=worker_calls_1):

        conf_res_1 = client.post("/api/action/confirm")
        assert conf_res_1.status_code == 200
        conf_data_1 = json.loads(conf_res_1.data)
        assert conf_data_1["status"] == "success"

    # Ověření aktualizace položky 1 v DB
    item1_updated = db.get_listing_by_id("batch_item_1")
    assert item1_updated["price"] == 1800
    assert item1_updated["portal_states"]["bazos"]["portal_item_id"] == "333"

    # 2. Znovuvystavení položky 2
    with patch("threading.Thread.start"):
        res2 = client.post("/api/action/repost_with_new_price", json={
            "listing_id": "batch_item_2",
            "new_price": 3500,
            "target_domain": "sport.bazos.cz"
        })
        assert res2.status_code == 200

    # Potvrzení položky 2
    mock_status_2 = {
        "state": "ready_for_review",
        "action_type": "repost",
        "listing_id": "batch_item_2",
        "meta": {
            "staged_price": 3500,
            "old_portal_url": "https://sport.bazos.cz/inzerat/222",
            "old_portal_item_id": "222",
            "auto_delete_old": True
        }
    }
    worker_calls_2 = [
        {"still_on_form": False, "new_url": "https://sport.bazos.cz/inzerat/444/kolo-2-nove.php"},
        {"success": True, "status": "deleted", "reason": "Vymazán"}
    ]
    with patch("app.action_state_mgr.get_status", return_value=mock_status_2),          patch("app.session_manager.run_on_worker", side_effect=worker_calls_2):

        conf_res_2 = client.post("/api/action/confirm")
        assert conf_res_2.status_code == 200

    item2_updated = db.get_listing_by_id("batch_item_2")
    assert item2_updated["price"] == 3500
    assert item2_updated["portal_states"]["bazos"]["portal_item_id"] == "444"


def test_batch_photo_helper_functions(tmp_path):
    """Ověří pomocné backendové funkce pro hromadnou správu fotek."""
    # 1. count_photos s různými příponami a vyloučeními
    photos_dir = tmp_path / "item_photos"
    photos_dir.mkdir()
    (photos_dir / "img1.jpg").write_text("dummy")
    (photos_dir / "img2.PNG").write_text("dummy")
    (photos_dir / "img3.jpeg").write_text("dummy")
    (photos_dir / "img4.jpg").write_text("dummy")
    (photos_dir / "doc.pdf").write_text("dummy")
    (photos_dir / ".DS_Store").write_text("dummy")

    # count_photos podporuje .jpg, .jpeg, .png
    total, included = count_photos(str(photos_dir), excluded_list=["img1.jpg", "img3.jpeg"])
    assert total == 4
    assert included == 2

    # Neexistující adresář
    total_none, included_none = count_photos(str(tmp_path / "nonexistent_dir"), [])
    assert total_none == 0
    assert included_none == 0

    # 2. safe_resolve_photos_dir
    with patch("listing_hub.agent.api.PHOTOS_DIR", tmp_path / "photos"):
        base_photos = tmp_path / "photos"
        base_photos.mkdir(exist_ok=True)
        valid_sub = base_photos / "ad_123"
        valid_sub.mkdir()

        # Platná relativní podsložka
        res_valid = safe_resolve_photos_dir("ad_123")
        assert res_valid == valid_sub.resolve()

        # Path traversal útok
        assert safe_resolve_photos_dir("../../etc/passwd") is None
        assert safe_resolve_photos_dir("..") is None

        # Prázdný nebo None vstup
        assert safe_resolve_photos_dir("") is None
        assert safe_resolve_photos_dir(None) is None


def test_batch_listings_lifecycle_filtering(client, clean_listings):
    """Ověří hromadné dotazování a filtrování inzerátů podle stavu (Agent API)."""
    # 2 Aktivní
    db.save_listing({"id": "act_1", "title": "Aktivní 1", "price": 100}, {"bazos": {"url": "https://bazos.cz/1", "status": "Aktivní"}})
    db.save_listing({"id": "act_2", "title": "Aktivní 2", "price": 200}, {"bazos": {"url": "https://bazos.cz/2", "status": "Aktivní"}})
    # 2 Koncepty (bez URL)
    db.save_listing({"id": "draft_1", "title": "Koncept 1", "price": 300}, {"bazos": {"url": "", "status": "Koncept"}})
    db.save_listing({"id": "draft_2", "title": "Koncept 2", "price": 400}, {"bazos": {"url": "", "status": "Koncept"}})
    # 1 Prodaný
    db.save_listing({"id": "sold_1", "title": "Prodaný 1", "price": 500}, {"bazos": {"url": "https://bazos.cz/3", "status": "Prodané"}})
    db.mark_listing_as_sold("sold_1", sale_price=450)

    # Summary endpoint
    res_sum = client.get("/api/agent/v1/summary")
    assert res_sum.status_code == 200
    s = json.loads(res_sum.data)["summary"]
    assert s["total_listings"] == 5
    assert s["active_count"] == 2
    assert s["draft_count"] == 2
    assert s["sold_count"] == 1

    # Listings filter by status
    res_drafts = client.get("/api/agent/v1/listings?status=draft")
    assert json.loads(res_drafts.data)["count"] == 2

    res_sold = client.get("/api/agent/v1/listings?status=sold")
    assert json.loads(res_sold.data)["count"] == 1

    res_search = client.get("/api/agent/v1/listings?search=Koncept")
    assert json.loads(res_search.data)["count"] == 2

    # Limit param
    res_limit = client.get("/api/agent/v1/listings?limit=2")
    assert json.loads(res_limit.data)["count"] == 2


# ============================================================================
# 5. Sold Statistics Under Extreme Values (get_sold_statistics)
# ============================================================================

def test_sold_statistics_zero_sales_in_database(clean_listings):
    """Ověří statistiku prodaných věcí při nulových prodejích v DB."""
    # 1. Zcela prázdná databáze
    stats_empty = db.get_sold_statistics()
    assert stats_empty == {
        "total_sold": 0,
        "total_profit": 0,
        "avg_price": 0
    }

    # 2. Databáze obsahuje pouze aktivní a draft inzeráty
    db.save_listing({"id": "item_active", "title": "Aktivní inzerát", "price": 1000}, {"bazos": {"status": "Aktivní", "url": "https://bazos.cz/1"}})
    db.save_listing({"id": "item_draft", "title": "Koncept inzerátu", "price": 2000}, {"bazos": {"status": "Koncept", "url": ""}})
    db.save_listing({"id": "item_expired", "title": "Expirovaný inzerát", "price": 3000}, {"bazos": {"status": "Expirováno", "url": "https://bazos.cz/2"}})

    stats_no_sold = db.get_sold_statistics()
    assert stats_no_sold == {
        "total_sold": 0,
        "total_profit": 0,
        "avg_price": 0
    }


def test_sold_statistics_negative_discount_sold_above_listed_price(clean_listings):
    """Ověří situaci, kdy se inzerát prodá dráž než byla inzerovaná cena (záporná sleva / přirážka)."""
    # Inzerovaná cena: 1000 Kč, prodáno za: 1500 Kč (např. příhoz zájemce / dražší balné)
    db.save_listing({"id": "item_premium", "title": "Sběratelská mince", "price": 1000}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("item_premium", sale_price=1500, sold_at="2026-09-12", notes="Kupující přihodil 500 Kč")

    stats = db.get_sold_statistics()
    assert stats["total_sold"] == 1
    assert stats["total_profit"] == 1500, "Statistika musí započítat reálnou prodejní cenu (1500 Kč), nikoli původních 1000 Kč"
    assert stats["avg_price"] == 1500

    # Přidáme inzerát s nulovou původní cenou (daruji za odvoz / 0 Kč), ale prodán za 200 Kč na pivo
    db.save_listing({"id": "item_free", "title": "Křeslo za odvoz", "price": 0}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("item_free", sale_price=200)

    # Přidáme inzerát s klasickou slevou: cena 5000 Kč, prodáno za 4000 Kč
    db.save_listing({"id": "item_discounted", "title": "Horský bicykl", "price": 5000}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("item_discounted", sale_price=4000)

    # Přidáme inzerát bez explicitní sale_price (sale_price=None -> fallback na price)
    db.save_listing({"id": "item_exact", "title": "Monitor Dell", "price": 3000}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("item_exact", sale_price=None)

    combined_stats = db.get_sold_statistics()
    assert combined_stats["total_sold"] == 4
    # 1500 + 200 + 4000 + 3000 = 8700 Kč
    assert combined_stats["total_profit"] == 8700
    # 8700 / 4 = 2175 Kč
    assert combined_stats["avg_price"] == 2175


def test_sold_statistics_large_volume_of_sold_listings(clean_listings):
    """Ověří výpočet statistik při velkém objemu stovek prodaných inzerátů."""
    total_items = 250
    expected_profit = 0

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        for i in range(1, total_items + 1):
            item_id = f"bulk_sold_{i}"
            # Různé ceny: 100 Kč, 200 Kč ... 25000 Kč
            price = i * 100
            expected_profit += price
            cursor.execute("""
                INSERT INTO listings (id, title, price, sale_price, sold_at)
                VALUES (?, ?, ?, ?, '2026-09-10')
            """, (item_id, f"Hromadný inzerát {i}", price, price))
            cursor.execute("""
                INSERT INTO portal_states (listing_id, portal_name, status)
                VALUES (?, 'bazos', 'Prodané')
            """, (item_id,))
        conn.commit()
    finally:
        conn.close()

    stats = db.get_sold_statistics()
    assert stats["total_sold"] == total_items
    assert stats["total_profit"] == expected_profit
    expected_avg = round(expected_profit / total_items)
    assert stats["avg_price"] == expected_avg


def test_sold_statistics_large_financial_amounts_multi_millions(clean_listings):
    """Ověří, že výpočet statistik zvládá vysoké finanční částky v řádu desítek milionů bez přetečení."""
    db.save_listing({"id": "heavy_machinery", "title": "Mobilní drtič kamene", "price": 45000000}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("heavy_machinery", sale_price=42000000)

    db.save_listing({"id": "real_estate", "title": "Komerční areál Budex", "price": 85000000}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("real_estate", sale_price=88000000)  # Záporná sleva

    stats = db.get_sold_statistics()
    assert stats["total_sold"] == 2
    assert stats["total_profit"] == 130000000  # 42M + 88M
    assert stats["avg_price"] == 65000000     # 130M / 2


def test_sold_statistics_endpoint_and_integer_rounding(client, clean_listings):
    """Ověří formátování a zaokrouhlování endpointu /api/listings/sold_stats."""
    # 3 položky s lichým součtem: 100 + 100 + 102 = 302 / 3 = 100.666... -> zaokrouhlí se na 101
    db.save_listing({"id": "round_1", "title": "Předmět 1", "price": 100}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("round_1", sale_price=100)

    db.save_listing({"id": "round_2", "title": "Předmět 2", "price": 100}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("round_2", sale_price=100)

    db.save_listing({"id": "round_3", "title": "Předmět 3", "price": 102}, {"bazos": {"status": "Aktivní"}})
    db.mark_listing_as_sold("round_3", sale_price=102)

    res = client.get("/api/listings/sold_stats")
    assert res.status_code == 200
    data = json.loads(res.data)

    assert data["status"] == "success"
    assert data["total_sold"] == 3
    assert data["total_profit"] == 302
    assert data["avg_price"] == 101
    assert isinstance(data["avg_price"], int)

    # Ověříme i vnitřní objekt stats
    assert data["stats"]["total_sold"] == 3
    assert data["stats"]["total_profit"] == 302
    assert data["stats"]["avg_price"] == 101
