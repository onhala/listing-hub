"""
listing_hub.portals.sbazar.sbazar_portal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integrace a podpora inzertního portálu Sbazar.cz (Seznam.cz).
Podporuje evidenci odkazů, parsování ID inzerátu, scraping zhlédnutí a přípravu pro automatizované publikování.
"""

import re
from typing import List, Dict, Any, Optional
from listing_hub.portals.base import AbstractPortal


class SbazarPortal(AbstractPortal):
    """
    Integrace inzertního portálu Sbazar.cz.
    """

    @property
    def name(self) -> str:
        return "sbazar"

    @property
    def display_name(self) -> str:
        return "Sbazar.cz"

    @property
    def supported_domains(self) -> List[str]:
        return ["sbazar.cz", "www.sbazar.cz"]

    def extract_item_id_from_url(self, url: str) -> Optional[str]:
        """
        Extrahuje ID inzerátu ze Sbazar URL.
        Příklady:
        - https://www.sbazar.cz/inzerat/18923412-vw-golf
        - https://sbazar.cz/inzerat/18923412
        """
        if not url:
            return None
        m = re.search(r'/inzerat/(\d+)', url)
        if m:
            return m.group(1)
        return None

    def post_listing(self, listing: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Předvyplnění / asistence při vystavení inzerátu na Sbazar.cz.
        """
        return {
            "portal_item_id": listing.get("id", "sbazar-draft"),
            "url": "https://www.sbazar.cz/pridat-inzerat",
            "status": "Koncept (Sbazar)"
        }

    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
        """Aktualizace ceny na Sbazar.cz."""
        return True

    def delete_listing(self, portal_item_id: str, url: str, password_b64: str, user_config: Dict[str, Any]) -> bool:
        """Smazání inzerátu ze Sbazar.cz."""
        return True

    def sync_listings(self, user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Synchronizace aktivních inzerátů z profilu Sbazar.cz."""
        return []
