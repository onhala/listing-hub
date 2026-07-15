from typing import List, Dict, Any
from listing_hub.portals.base import AbstractPortal
from listing_hub.portals.bazos.session import session_manager
from listing_hub.portals.bazos.categories import extract_ad_id, extract_subdomain, get_target_domain

# Prozatím importujeme legacy implementace z post_to_bazos.py,
# abychom zajistili bezchybný běh před kompletním přesunem.
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
import post_to_bazos

class BazosPortal(AbstractPortal):
    """
    Implementace inzertního portálu Bazoš.cz.
    """

    @property
    def name(self) -> str:
        return "bazos"

    @property
    def display_name(self) -> str:
        return "Bazoš.cz"

    def post_listing(self, listing: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        # Volá stávající Playwright automatizaci
        success = post_to_bazos.run_playwright_action(
            ad=listing,
            user_config=user_config,
            action="post",
            is_web=True
        )
        if success:
            # Po publikaci Bazoš scraper obvykle aktualizuje data a uloží URL.
            # Zkusíme dohledat URL z dat, která byla uložena v JSONu nebo najít podle názvu.
            # Vracíme placeholder/odkaz pokud ho máme
            url = listing.get("url") or ""
            return {
                "portal_item_id": extract_ad_id(url),
                "url": url,
                "status": "Aktivní"
            }
        raise Exception("Nepodařilo se vystavit inzerát na Bazoš.")

    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
        # Převedeme inzerát na kompatibilní slovník pro legacy kód
        ad = {
            "title": "",
            "price": new_price,
            "url": url,
            "local_photos_dir": ""
        }
        return post_to_bazos.run_playwright_action(
            ad=ad,
            user_config=user_config,
            action="change_price",
            extra_val=str(new_price),
            is_web=True
        )

    def delete_listing(self, portal_item_id: str, url: str, password_b64: str, user_config: Dict[str, Any]) -> bool:
        ad = {
            "title": "",
            "url": url,
            "ad_password_b64": password_b64,
            "local_photos_dir": ""
        }
        return post_to_bazos.run_playwright_action(
            ad=ad,
            user_config=user_config,
            action="delete",
            is_web=True
        )

    def sync_listings(self, user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Provede synchronizaci Moje inzeráty
        # Legacy CLI synchronizace uloží data do JSON databáze, my je následně přečteme
        # a zkonvertujeme na standardní formát.
        post_to_bazos.cli_update_listings_from_bazos(
            user_config=user_config,
            is_web=True,
            is_auto_refresh=False
        )
        # Vrátíme načtená data z JSONu
        data, _ = post_to_bazos.load_data()
        result = []
        for item in data.get("active_listings", []):
            url = item.get("url", "")
            result.append({
                "portal_item_id": extract_ad_id(url),
                "title": item.get("title"),
                "url": url,
                "views": item.get("views", 0),
                "status": item.get("status", "Aktivní")
            })
        return result
