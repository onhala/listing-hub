from typing import List, Dict, Any
from listing_hub.portals.base import AbstractPortal

class AukroPortal(AbstractPortal):
    """
    Integrace Aukro.cz prostřednictvím oficiálního REST API (api.aukro.cz).
    """

    @property
    def name(self) -> str:
        return "aukro"

    @property
    def display_name(self) -> str:
        return "Aukro.cz"

    def post_listing(self, listing: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Implementovat OAuth2 autorizaci a POST /offers endpoint
        # Zde bude reálná integrace Aukro REST API.
        return {
            "portal_item_id": "aukro-draft-id",
            "url": "https://aukro.cz/moje-nabidky",
            "status": "Koncept (Aukro)"
        }

    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
        # TODO: Implementovat PUT /offers/{id}/price endpoint
        return True

    def delete_listing(self, portal_item_id: str, url: str, password_b64: str, user_config: Dict[str, Any]) -> bool:
        # TODO: Implementovat DELETE /offers/{id} nebo ukončení nabídky
        return True

    def sync_listings(self, user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: Implementovat GET /offers (stažení aktivních nabídek)
        return []
