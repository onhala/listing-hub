import pytest
from listing_hub.portals.bazos.categories import extract_ad_id, extract_subdomain, get_target_domain

def test_extract_ad_id():
    assert extract_ad_id("https://nabytek.bazos.cz/inzerat/123456789/krasny-stul.php") == "123456789"
    assert extract_ad_id("https://dum.bazos.cz/inzerat/987654321/nejaky-inzerat") == "987654321"
    assert extract_ad_id("https://nabytek.bazos.cz/inzerat/") is None
    assert extract_ad_id("") is None
    assert extract_ad_id(None) is None

def test_extract_subdomain():
    assert extract_subdomain("https://dum.bazos.cz/inzerat/123") == "dum.bazos.cz"
    assert extract_subdomain("https://nabytek.bazos.cz/inzerat/123") == "nabytek.bazos.cz"
    assert extract_subdomain("") == "dum.bazos.cz"
    assert extract_subdomain(None) == "dum.bazos.cz"

def test_get_target_domain():
    # Test based on original_url containing nabytek
    assert get_target_domain("Libovolný název", "https://nabytek.bazos.cz/inzerat/123") == "nabytek.bazos.cz"
    
    # Test based on furniture keywords in title
    assert get_target_domain("Krásný dřevěný stůl", "") == "nabytek.bazos.cz"
    assert get_target_domain("Jídelní židle", "") == "nabytek.bazos.cz"
    assert get_target_domain("Stará komoda z masivu", "") == "nabytek.bazos.cz"
    
    # Fallback to dum.bazos.cz
    assert get_target_domain("Aku vrtačka Bosch", "") == "dum.bazos.cz"
    assert get_target_domain("Sekačka na trávu", "https://dum.bazos.cz/inzerat/123") == "dum.bazos.cz"


def test_normalize_cz():
    from listing_hub.portals.bazos.categories import normalize_cz
    assert normalize_cz("Sekačka na trávu HECHT") == "sekacka na travu hecht"
    assert normalize_cz("Příliš žluťoučký kůň") == "prilis zlutoucky kun"
    assert normalize_cz("  Výkonný   drtič   větví!  ") == "vykonny drtic vetvi"


def test_match_best_category_option_garden():
    from listing_hub.portals.bazos.categories import match_best_category_option

    dum_options = [
        ("", "Vyberte kategorii"),
        ("bazeny", "Bazény"),
        ("cerpadla", "Čerpadla"),
        ("sekacky", "Sekačky"),
        ("technika", "Zahradní technika"),
        ("naradi", "Nářadí"),
        ("pily", "Pily"),
        ("ostatnidum", "Ostatní"),
    ]

    # Test drtič větví / štěpkovač
    val, lbl, score = match_best_category_option(
        dum_options,
        title="Výkonný drtič větví / štěpkovač ATIKA 2800 W + vak",
        description="Prodám zánovní zahradní drtič",
        category="Zahrada"
    )
    assert val == "technika"
    assert "Zahradní technika" in lbl

    # Test sekačka s pojezdem
    val, lbl, score = match_best_category_option(
        dum_options,
        title="Sekačka HECHT 548 SWE s pojezdem",
        description="Benzínová sekačka na trávu",
        category="Zahrada"
    )
    assert val == "sekacky"

    # Test strunová sekačka
    val, lbl, score = match_best_category_option(
        dum_options,
        title="Elektrická strunová sekačka AL-KO",
        description="Lehká strunovka na dosekávání",
        category="Zahrada"
    )
    assert val == "sekacky"

    # Test nářadí / aku vrtačka
    val, lbl, score = match_best_category_option(
        dum_options,
        title="Aku vrtačka Bosch Professional",
        description="Kompletní kufr s bity",
        category="Dílna"
    )
    assert val == "naradi"


def test_match_best_category_option_furniture():
    from listing_hub.portals.bazos.categories import match_best_category_option

    nabytek_options = [
        ("", "Vyberte kategorii"),
        ("jidelnikouty", "Jídelní kouty"),
        ("kresla", "Křesla a gauče"),
        ("postele", "Postele"),
        ("skrine", "Skříně"),
        ("stoly", "Stoly"),
        ("zidle", "Židle"),
        ("ostatninabytek", "Ostatní nábytek"),
    ]

    # Test jídelní stůl
    val, lbl, score = match_best_category_option(
        nabytek_options,
        title="Retro rozkládací jídelní stůl",
        description="Zachovalý stůl do kuchyně",
        category="Nábytek"
    )
    assert val == "stoly"

    # Test křeslo ušák
    val, lbl, score = match_best_category_option(
        nabytek_options,
        title="Křeslo ušák IKEA Strandmon",
        description="Pohodlné křeslo žluté barvy",
        category="Nábytek"
    )
    assert val == "kresla"


def test_bazos_all_subdomains_contains_all_20_sections():
    from listing_hub.portals.bazos.categories import BAZOS_ALL_SUBDOMAINS
    assert len(BAZOS_ALL_SUBDOMAINS) == 20
    domains = [s["domain"] for s in BAZOS_ALL_SUBDOMAINS]
    assert "deti.bazos.cz" in domains
    assert "dum.bazos.cz" in domains
    assert "nabytek.bazos.cz" in domains
    assert "sport.bazos.cz" in domains
    assert "auto.bazos.cz" in domains
    assert "mobil.bazos.cz" in domains
    assert "foto.bazos.cz" in domains
    assert "hudba.bazos.cz" in domains
    assert "knihy.bazos.cz" in domains
    assert "zvirata.bazos.cz" in domains
    assert "ostatni.bazos.cz" in domains


def test_rank_target_domains_comprehensive():
    from listing_hub.portals.bazos.categories import rank_target_domains

    # 1. Plameňák / Děti
    res_deti = rank_target_domains("XXL Plameňák ostrov pro 5 osob - TOP stav")
    assert res_deti[0]["domain"] == "deti.bazos.cz"
    assert "plamenak" in res_deti[0]["matched_keywords"]

    # 2. Kočárek / Děti
    res_kocar = rank_target_domains("Dětský kočárek Cybex Priam", description="Kombinovaný kočárek pro miminko")
    assert res_kocar[0]["domain"] == "deti.bazos.cz"

    # 3. iPhone / Mobil
    res_mobil = rank_target_domains("Apple iPhone 15 Pro 128GB Black Titanium")
    assert res_mobil[0]["domain"] == "mobil.bazos.cz"

    # 4. Kytara / Hudba
    res_hudba = rank_target_domains("Akustická kytara Fender CD-60")
    assert res_hudba[0]["domain"] == "hudba.bazos.cz"

    # 5. Drtič větví / Dům a zahrada
    res_dum = rank_target_domains("Výkonný drtič větví / štěpkovač ATIKA 2800 W + vak")
    assert res_dum[0]["domain"] == "dum.bazos.cz"

    # 6. Soustruh / Stroje
    res_stroje = rank_target_domains("Hrotový soustruh na kov Bernardo")
    assert res_stroje[0]["domain"] == "stroje.bazos.cz"

    # 7. Zachování původní URL subdomény jako top preference
    res_url = rank_target_domains("Univerzální předmět", original_url="https://sport.bazos.cz/inzerat/123")
    assert res_url[0]["domain"] == "sport.bazos.cz"
    assert res_url[0]["score"] >= 1000


