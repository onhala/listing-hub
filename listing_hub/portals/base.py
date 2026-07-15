from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AbstractPortal(ABC):
    """
    Abstraktní třída definující rozhraní pro integraci jakéhokoliv inzertního portálu.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unikátní název portálu (např. 'bazos', 'aukro')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Lidsky čitelný název (např. 'Bazoš.cz', 'Aukro.cz')."""
        pass

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
