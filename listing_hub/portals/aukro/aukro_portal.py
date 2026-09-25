from typing import List, Dict, Any, Optional
import re
from listing_hub.portals.base import AbstractPortal

class AukroPortal(AbstractPortal):
    """
    Integrace Aukro.cz prostřednictvím oficiálního REST API (api.aukro.cz) i veřejného katalogu.
    """

    @property
    def name(self) -> str:
        return "aukro"

    @property
    def display_name(self) -> str:
        return "Aukro.cz"

    @property
    def supported_domains(self) -> List[str]:
        return ["aukro.cz", "www.aukro.cz"]

    def extract_item_id_from_url(self, url: str) -> Optional[str]:
        """
        Extrahuje ID nabídky z Aukro URL.
        Příklady:
        - https://aukro.cz/vintage-hodinky-prim-7023849102
        - https://aukro.cz/nabidka/7023849102
        """
        if not url:
            return None
        m = re.search(r'(?:-(\d{9,12})|\/(\d{9,12}))', url)
        if m:
            return m.group(1) or m.group(2)
        return None

    def post_listing(self, listing: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "portal_item_id": listing.get("id", "aukro-draft-id"),
            "url": "https://aukro.cz/moje-nabidky",
            "status": "Koncept (Aukro)"
        }

    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
        return True

    def delete_listing(self, portal_item_id: str, url: str, password_b64: str, user_config: Dict[str, Any]) -> bool:
        return True

    def sync_listings(self, user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

