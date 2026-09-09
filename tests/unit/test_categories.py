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

