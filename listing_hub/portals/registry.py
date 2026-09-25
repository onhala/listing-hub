"""
listing_hub.portals.registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centrální registr všech podporovaných inzertních portálů v Listing Hubu.
Umožňuje dynamické vyhledávání portálu podle jména nebo URL adresy,
registraci nových custom portálů a jednotný přístup k životnímu cyklu inzerátů.
"""

from typing import Dict, List, Optional
from listing_hub.portals.base import AbstractPortal
from listing_hub.portals.bazos.bazos_portal import BazosPortal
from listing_hub.portals.aukro.aukro_portal import AukroPortal
from listing_hub.portals.sbazar.sbazar_portal import SbazarPortal
from listing_hub.portals.vinted.vinted_portal import VintedPortal
from listing_hub.portals.facebook.facebook_portal import FacebookMarketplacePortal


class PortalRegistry:
    """
    Správce a registr všech inzertních portálů v ekosystému Listing Hub.
    """

    def __init__(self):
        self._portals: Dict[str, AbstractPortal] = {}
        
        # Registrace výchozích portálů
        self.register(BazosPortal())
        self.register(AukroPortal())
        self.register(SbazarPortal())
        self.register(VintedPortal())
        self.register(FacebookMarketplacePortal())

    def register(self, portal: AbstractPortal) -> None:
        """Zaregistruje instanci portálu do systému."""
        if not isinstance(portal, AbstractPortal):
            raise TypeError(f"Objekt {portal} musí dědit z AbstractPortal.")
        self._portals[portal.name] = portal

    def unregister(self, name: str) -> bool:
        """Odregistruje portál podle strojového názvu."""
        if name in self._portals:
            del self._portals[name]
            return True
        return False

    def has_portal(self, name: str) -> bool:
        """Ověří, zda je portál daného názvu zaregistrován."""
        return name in self._portals

    def get_portal(self, name: str) -> AbstractPortal:
        """Vrátí instanci portálu podle jeho jména."""
        if name not in self._portals:
            raise ValueError(f"Portál '{name}' není registrován v systému. Dostupné portály: {self.get_portal_names()}")
        return self._portals[name]

    def get_portal_or_none(self, name: str) -> Optional[AbstractPortal]:
        """Vrátí instanci portálu nebo None, pokud není registrován."""
        return self._portals.get(name)

    def list_portals(self) -> List[AbstractPortal]:
        """Vrátí seznam všech registrovaných instancí portálů."""
        return list(self._portals.values())

    def get_portal_names(self) -> List[str]:
        """Vrátí seznam identifikátorů všech registrovaných portálů."""
        return list(self._portals.keys())

    def detect_portal_from_url(self, url: str) -> Optional[AbstractPortal]:
        """
        Automaticky detekuje a vrátí odpovídající portál podle domény v zadané URL.
        """
        if not url:
            return None
        for portal in self._portals.values():
            if portal.validate_url(url):
                return portal
        return None

    def scrape_views_for_portal(self, portal_name: str, url: str) -> Optional[int]:
        """
        Provede scraping zhlédnutí pro zadaný portál a URL.
        Pokud portál není v registru, zkusí detekci podle URL nebo univerzální scraper.
        """
        if not url:
            return None
            
        portal = self.get_portal_or_none(portal_name)
        if not portal:
            portal = self.detect_portal_from_url(url)
            
        if portal:
            return portal.scrape_views(url)
            
        # Fallback na univerzální scraper
        try:
            from listing_hub.portals.scrapers.universal import scrape_listing_views
            return scrape_listing_views(url)
        except Exception:
            return None


# Globální singleton registru portálů
portal_registry = PortalRegistry()
