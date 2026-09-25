from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import urllib.parse
import re

class AbstractPortal(ABC):
    """
    Abstraktní bázová třída definující unifikované rozhraní pro integraci jakéhokoliv inzertního portálu
    (Bazoš, Aukro, Sbazar, Vinted, Facebook Marketplace atd.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unikátní strojový identifikátor portálu (např. 'bazos', 'aukro', 'sbazar', 'vinted', 'fb_marketplace')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Lidsky čitelný název (např. 'Bazoš.cz', 'Aukro.cz', 'Sbazar.cz')."""
        pass

    @property
    def supported_domains(self) -> List[str]:
        """Seznam podporovaných doménových jmen pro automatickou detekci URL."""
        return []

    def validate_url(self, url: str) -> bool:
        """Ověří, zda zadaná URL patří k tomuto portálu."""
        if not url:
            return False
        try:
            parsed = urllib.parse.urlparse(url.lower())
            domain = parsed.netloc
            if not self.supported_domains:
                return self.name in domain
            return any(d in domain for d in self.supported_domains)
        except Exception:
            return False

    def normalize_url(self, raw_url: str) -> str:
        """Normalizuje URL inzerátu (odstraní sledovací parametry jako utm_*, fbclid apod.)."""
        if not raw_url:
            return ""
        try:
            parsed = urllib.parse.urlparse(raw_url.strip())
            query_params = urllib.parse.parse_qs(parsed.query)
            # Odstraníme běžné sledovací parametry
            cleaned_params = {k: v for k, v in query_params.items() if not k.startswith("utm_") and k not in ("fbclid", "gclid", "ref")}
            cleaned_query = urllib.parse.urlencode(cleaned_params, doseq=True)
            normalized = urllib.parse.urlunparse((
                parsed.scheme or "https",
                parsed.netloc,
                parsed.path,
                parsed.params,
                cleaned_query,
                ""  # Odstraníme fragment #...
            ))
            return normalized.rstrip("?")
        except Exception:
            return raw_url.strip()

    def extract_item_id_from_url(self, url: str) -> Optional[str]:
        """Extrahuje unikátní ID inzerátu z veřejné URL adresy portálu."""
        return None

    def scrape_views(self, url: str) -> Optional[int]:
        """
        Získá aktuální počet zhlédnutí inzerátu z veřejné URL.
        Výchozí implementace deleguje na univerzální scraper.
        """
        try:
            from listing_hub.portals.scrapers.universal import scrape_listing_views
            return scrape_listing_views(url)
        except Exception:
            return None

    def get_top_info(self, url: str) -> Dict[str, Any]:
        """
        Vrací informace o topování a zvýraznění inzerátu.
        {
            "is_top": bool,
            "top_expires_at": Optional[str],
            "top_info": Optional[str]
        }
        """
        return {
            "is_top": False,
            "top_expires_at": None,
            "top_info": None
        }

    @abstractmethod
    def post_listing(self, listing: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Vystaví inzerát na portál.
        Vrací slovník s informacemi o nově vystaveném inzerátu:
        {
            "portal_item_id": "12345",
            "url": "https://...",
            "status": "Aktivní"
        }
        """
        pass

    @abstractmethod
    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
        """Aktualizuje cenu inzerátu na portálu."""
        pass

    @abstractmethod
    def delete_listing(self, portal_item_id: str, url: str, password_b64: str, user_config: Dict[str, Any]) -> bool:
        """Smaže inzerát z portálu."""
        pass

    @abstractmethod
    def sync_listings(self, user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Stáhne aktuální seznam aktivních inzerátů uživatele z portálu.
        Vrací list slovníků:
        [
            {
                "portal_item_id": "12345",
                "title": "Nadpis",
                "url": "https://...",
                "views": 42,
                "status": "Aktivní"
            },
            ...
        ]
        """
        pass

