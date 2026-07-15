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
