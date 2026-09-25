"""
listing_hub.portals.facebook.facebook_portal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integrace a podpora pro Facebook Marketplace.
Podporuje evidenci odkazů, parsování ID inzerátu z marketplace/item/..., scraping a asistenci.
"""

import re
from typing import List, Dict, Any, Optional
from listing_hub.portals.base import AbstractPortal


class FacebookMarketplacePortal(AbstractPortal):
    """
    Integrace pro Facebook Marketplace.
    """

    @property
    def name(self) -> str:
        return "fb_marketplace"

    @property
    def display_name(self) -> str:
        return "Facebook Marketplace"

    @property
    def supported_domains(self) -> List[str]:
        return ["facebook.com", "www.facebook.com", "m.facebook.com", "fb.com"]

    def extract_item_id_from_url(self, url: str) -> Optional[str]:
        """
        Extrahuje ID inzerátu z Facebook Marketplace URL.
        Příklady:
        - https://www.facebook.com/marketplace/item/102938475619283/
        - https://facebook.com/marketplace/item/102938475619283
        """
        if not url:
            return None
        m = re.search(r'/marketplace/item/(\d+)', url)
        if m:
            return m.group(1)
        return None

    def post_listing(self, listing: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Předvyplnění / asistence při vystavení inzerátu na Facebook Marketplace.
        """
        return {
            "portal_item_id": listing.get("id", "fb-draft"),
            "url": "https://www.facebook.com/marketplace/create",
            "status": "Koncept (Facebook Marketplace)"
        }

    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
        """Aktualizace ceny na Facebook Marketplace."""
        return True

    def delete_listing(self, portal_item_id: str, url: str, password_b64: str, user_config: Dict[str, Any]) -> bool:
        """Smazání inzerátu z Facebook Marketplace."""
        return True

    def sync_listings(self, user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Synchronizace aktivních inzerátů z profilu Facebook Marketplace."""
        return []
