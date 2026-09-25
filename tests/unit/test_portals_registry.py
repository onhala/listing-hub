"""
tests.unit.test_portals_registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit testy pro abstraktní portálovou vrstvu, registraci portálů (PortalRegistry)
a jednotlivé portálové adaptéry (Bazoš, Aukro, Sbazar, Vinted, Facebook Marketplace).
"""

import pytest
from unittest.mock import patch, MagicMock

from listing_hub.portals.base import AbstractPortal
from listing_hub.portals.registry import PortalRegistry, portal_registry
from listing_hub.portals.bazos.bazos_portal import BazosPortal
from listing_hub.portals.aukro.aukro_portal import AukroPortal
from listing_hub.portals.sbazar.sbazar_portal import SbazarPortal
from listing_hub.portals.vinted.vinted_portal import VintedPortal
from listing_hub.portals.facebook.facebook_portal import FacebookMarketplacePortal


class DummyCustomPortal(AbstractPortal):
    @property
    def name(self) -> str:
        return "dummy_portal"

    @property
    def display_name(self) -> str:
        return "Dummy Portal"

    @property
    def supported_domains(self):
        return ["dummy-portal.com", "custom.cz"]

    def extract_item_id_from_url(self, url: str):
        if "id=" in url:
            return url.split("id=")[-1]
        return None

    def post_listing(self, listing, user_config):
        return {"portal_item_id": "dummy-1", "url": "https://dummy-portal.com/ad/1", "status": "Aktivní"}

    def update_price(self, portal_item_id, new_price, url, user_config):
        return True

    def delete_listing(self, portal_item_id, url, password_b64, user_config):
        return True

    def sync_listings(self, user_config):
        return []


def test_abstract_portal_base_methods():
    portal = DummyCustomPortal()
    
    # 1. URL validace
    assert portal.validate_url("https://dummy-portal.com/item/123") is True
    assert portal.validate_url("https://custom.cz/ad/456") is True
    assert portal.validate_url("https://other-site.com/xyz") is False
    assert portal.validate_url("") is False
    assert portal.validate_url(None) is False

    # 2. URL normalizace (ořez tracking parametrů)
    dirty_url = "https://dummy-portal.com/item/123?utm_source=facebook&utm_medium=cpc&fbclid=IwAR0123&keep=1#section"
    clean_url = portal.normalize_url(dirty_url)
    assert "utm_source" not in clean_url
    assert "fbclid" not in clean_url
    assert "keep=1" in clean_url
    assert "#section" not in clean_url

    # 3. ID extraction
    assert portal.extract_item_id_from_url("https://dummy-portal.com/item?id=998877") == "998877"
    assert portal.extract_item_id_from_url("https://dummy-portal.com/item/plain") is None

    # 4. Top info defaults
    top_info = portal.get_top_info("https://dummy-portal.com/item/123")
    assert top_info["is_top"] is False
    assert top_info["top_expires_at"] is None


def test_portal_registry_lifecycle_and_lookup():
    reg = PortalRegistry()
    
    # Ověříme, že výchozí portály jsou přítomny
    assert reg.has_portal("bazos") is True
    assert reg.has_portal("aukro") is True
    assert reg.has_portal("sbazar") is True
    assert reg.has_portal("vinted") is True
    assert reg.has_portal("fb_marketplace") is True
    assert reg.has_portal("nonexistent") is False

    names = reg.get_portal_names()
    assert "bazos" in names
    assert "sbazar" in names

    # Vyhledání existujícího a neexistujícího portálu
    bazos = reg.get_portal("bazos")
    assert isinstance(bazos, BazosPortal)
    assert reg.get_portal_or_none("nonexistent") is None

    with pytest.raises(ValueError) as excinfo:
        reg.get_portal("invalid_portal_key")
    assert "není registrován" in str(excinfo.value)

    # Registrace nového custom portálu
    custom = DummyCustomPortal()
    reg.register(custom)
    assert reg.has_portal("dummy_portal") is True
    assert reg.get_portal("dummy_portal") == custom

    # Odregistrování
    assert reg.unregister("dummy_portal") is True
    assert reg.has_portal("dummy_portal") is False
    assert reg.unregister("dummy_portal") is False

    # Chybový typ při registraci
    with pytest.raises(TypeError):
        reg.register("NotAPortalInstance")


def test_portal_registry_detect_portal_from_url():
    reg = PortalRegistry()

    p_bazos = reg.detect_portal_from_url("https://auto.bazos.cz/inzerat/12345/auto.php")
    assert isinstance(p_bazos, BazosPortal)

    p_sbazar = reg.detect_portal_from_url("https://www.sbazar.cz/inzerat/1928374-vw-golf")
    assert isinstance(p_sbazar, SbazarPortal)

    p_vinted = reg.detect_portal_from_url("https://www.vinted.cz/items/49281-bunda")
    assert isinstance(p_vinted, VintedPortal)

    p_fb = reg.detect_portal_from_url("https://www.facebook.com/marketplace/item/102938475619283/")
    assert isinstance(p_fb, FacebookMarketplacePortal)

    p_aukro = reg.detect_portal_from_url("https://aukro.cz/nabidka/7023849102")
    assert isinstance(p_aukro, AukroPortal)

    assert reg.detect_portal_from_url("https://unknown-classifieds.de/item/1") is None
    assert reg.detect_portal_from_url("") is None


def test_sbazar_portal_adapter():
    sb = SbazarPortal()
    assert sb.name == "sbazar"
    assert sb.display_name == "Sbazar.cz"
    assert "sbazar.cz" in sb.supported_domains

    # Parsování ID
    assert sb.extract_item_id_from_url("https://www.sbazar.cz/inzerat/18923412-vw-golf-7") == "18923412"
    assert sb.extract_item_id_from_url("https://sbazar.cz/inzerat/998811") == "998811"
    assert sb.extract_item_id_from_url("https://sbazar.cz/moje-inzeraty") is None
    assert sb.extract_item_id_from_url("") is None

    # Post / Price / Delete stubs
    listing = {"id": "item-123", "title": "Golf"}
    posted = sb.post_listing(listing, {})
    assert posted["portal_item_id"] == "item-123"
    assert "sbazar.cz" in posted["url"]
    assert sb.update_price("item-123", 5000, "https://sbazar.cz", {}) is True
    assert sb.delete_listing("item-123", "https://sbazar.cz", "pass", {}) is True
    assert sb.sync_listings({}) == []


def test_vinted_portal_adapter():
    vp = VintedPortal()
    assert vp.name == "vinted"
    assert vp.display_name == "Vinted.cz"
    assert "vinted.cz" in vp.supported_domains

    # Parsování ID
    assert vp.extract_item_id_from_url("https://www.vinted.cz/items/45920192-bunda-nike-air") == "45920192"
    assert vp.extract_item_id_from_url("https://vinted.com/items/776655") == "776655"
    assert vp.extract_item_id_from_url("https://vinted.cz/member/items") is None

    listing = {"id": "vinted-123", "title": "Bunda"}
    posted = vp.post_listing(listing, {})
    assert posted["portal_item_id"] == "vinted-123"
    assert "vinted.cz" in posted["url"]
    assert vp.update_price("vinted-123", 800, "https://vinted.cz", {}) is True
    assert vp.delete_listing("vinted-123", "https://vinted.cz", "", {}) is True
    assert vp.sync_listings({}) == []


def test_facebook_marketplace_portal_adapter():
    fb = FacebookMarketplacePortal()
    assert fb.name == "fb_marketplace"
    assert fb.display_name == "Facebook Marketplace"
    assert "facebook.com" in fb.supported_domains

    # Parsování ID
    assert fb.extract_item_id_from_url("https://www.facebook.com/marketplace/item/102938475619283/") == "102938475619283"
    assert fb.extract_item_id_from_url("https://m.facebook.com/marketplace/item/9988776655443322") == "9988776655443322"
    assert fb.extract_item_id_from_url("https://facebook.com/marketplace/inbox") is None

    listing = {"id": "fb-item-1", "title": "Stůl"}
    posted = fb.post_listing(listing, {})
    assert posted["portal_item_id"] == "fb-item-1"
    assert "facebook.com" in posted["url"]
    assert fb.update_price("fb-item-1", 1200, "https://facebook.com", {}) is True
    assert fb.delete_listing("fb-item-1", "https://facebook.com", "", {}) is True
    assert fb.sync_listings({}) == []


def test_portal_registry_scrape_views_routing():
    reg = PortalRegistry()

    # Test přímého volání přes registry
    with patch("listing_hub.portals.scrapers.universal.scrape_listing_views", return_value=142):
        views = reg.scrape_views_for_portal("sbazar", "https://www.sbazar.cz/inzerat/123-test")
        assert views == 142

        # Automatická detekce portálu z URL pokud je název portálu custom / neznámý
        views_detected = reg.scrape_views_for_portal("custom", "https://www.vinted.cz/items/456-test")
        assert views_detected == 142

    # Prázdná URL vrací None bez chyb
    assert reg.scrape_views_for_portal("bazos", "") is None
    assert reg.scrape_views_for_portal("bazos", None) is None
