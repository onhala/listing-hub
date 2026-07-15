from typing import List, Dict, Any
from datetime import datetime
import uuid
import re
from listing_hub.portals.base import AbstractPortal
from listing_hub.portals.bazos.session import session_manager
from listing_hub.portals.bazos.categories import extract_ad_id, extract_subdomain, get_target_domain
from listing_hub.portals.bazos.date_parser import parse_bazos_date
from listing_hub.core.db import save_listing, get_all_listings, get_db_connection
from listing_hub.core.config import PHOTOS_DIR
from listing_hub.portals.bazos.scraper import scrape_listings_from_html

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
            url = listing.get("url") or ""
            return {
                "portal_item_id": extract_ad_id(url),
                "url": url,
                "status": "Aktivní"
            }
        raise Exception("Nepodařilo se vystavit inzerát na Bazoš.")

    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
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
        """
        Stáhne inzeráty z Bazoše, spáruje je se SQLite databází,
        automaticky naimportuje nově nalezené cizí inzeráty a aktualizuje stavy.
        """
        # Spustíme scrape inzerátů z Bazoše
        # Získáme seznam z Bazoše pomocí metody z post_to_bazos
        # (dočasně využijeme vnitřní logiku scraperu z post_to_bazos)
        try:
            _, browser, _, page = session_manager.get_session()
        except Exception as e:
            raise Exception(f"Nepodařilo se připojit k prohlížeči Bazoše: {e}")

        # Přejdeme na Moje inzeráty
        page.goto("https://www.bazos.cz/moje-inzeraty.php")
        
        # Přihlášení
        try:
            email_input = page.locator("input[name='mail']")
            phone_input = page.locator("input[name='telefon']")
            if email_input.is_visible(timeout=3000):
                email_val = user_config.get("email", "")
                phone_val = user_config.get("phone", "")
                email_input.fill(email_val)
                phone_input.fill(phone_val)
                
                list_btn = page.locator("input[type='submit'][value='Vypsat inzeráty']")
                if list_btn.is_visible(timeout=2000):
                    list_btn.click()
                else:
                    submit_btn = page.locator("input[type='submit'][value='Ověřit']")
                    submit_btn.click()
                    # Čekáme na kód
                    code_input = page.locator("input[name='kodd']")
                    code_input.wait_for(timeout=10000)
                    # Čekáme na ruční zadání v noVNC
                    page.wait_for_selector("input[name='kodd']", state="hidden", timeout=60000)
        except Exception:
            pass

        # Stáhneme inzeráty z HTML
        html_content = page.content()
        scraped_listings = scrape_listings_from_html(html_content)
        
        # Načteme lokální inzeráty z SQLite
        local_listings = get_all_listings()
        matched_scraped_indices = set()
        
        result = []
        
        # 1. Spárujeme stávající SQLite inzeráty a aktualizujeme je
        for local_ad in local_listings:
            bazos_state = local_ad.get("portal_states", {}).get("bazos", {})
            local_url = bazos_state.get("url", "").strip()
            
            best_scraped_match = None
            best_scraped_idx = -1
            
            # Match podle URL
            if local_url:
                for s_idx, scraped_ad in enumerate(scraped_listings):
                    if s_idx in matched_scraped_indices:
                        continue
                    if scraped_ad["url"].strip() == local_url:
                        best_scraped_match = scraped_ad
                        best_scraped_idx = s_idx
                        break
                        
            # Match podle nadpisu (prvních 50 znaků)
            if not best_scraped_match:
                local_title_50 = local_ad["title"][:50].lower().strip()
                for s_idx, scraped_ad in enumerate(scraped_listings):
                    if s_idx in matched_scraped_indices:
                        continue
                    scraped_title_50 = scraped_ad["title"][:50].lower().strip()
                    if scraped_title_50 == local_title_50:
                        best_scraped_match = scraped_ad
                        best_scraped_idx = s_idx
                        break
            
            if best_scraped_match:
                matched_scraped_indices.add(best_scraped_idx)
                
                # Aktualizujeme stav v databázi
                portal_item_id = extract_ad_id(best_scraped_match["url"])
                
                # Přepočet stáří
                days_old_val = 0
                try:
                    dt = datetime.strptime(best_scraped_match["date_created"], "%Y-%m-%d")
                    days_old_val = (datetime.today() - dt).days
                except Exception:
                    pass
                
                local_ad["price"] = best_scraped_match["price"]
                local_ad["days_old"] = days_old_val
                
                bazos_state_data = {
                    "portal_item_id": portal_item_id,
                    "url": best_scraped_match["url"],
                    "status": "Aktivní",
                    "views": best_scraped_match["views"],
                    "last_synced": datetime.now().isoformat()
                }
                save_listing(local_ad, {"bazos": bazos_state_data})
                
                result.append({
                    "portal_item_id": portal_item_id,
                    "title": local_ad["title"],
                    "url": best_scraped_match["url"],
                    "views": best_scraped_match["views"],
                    "status": "Aktivní"
                })
            else:
                # Inzerát na Bazoši chybí -> Expiroval (pokud byl označen jako aktivní na Bazoši)
                if bazos_state and bazos_state.get("status") == "Aktivní":
                    bazos_state_data = {
                        "portal_item_id": bazos_state.get("portal_item_id"),
                        "url": bazos_state.get("url"),
                        "status": "Expirováno",
                        "views": bazos_state.get("views", 0),
                        "last_synced": datetime.now().isoformat()
                    }
                    save_listing(local_ad, {"bazos": bazos_state_data})
                    
        # 2. Automaticky importujeme nově nalezené inzeráty z Bazoše (cizí/externí inzeráty)
        for s_idx, scraped_ad in enumerate(scraped_listings):
            if s_idx in matched_scraped_indices:
                continue
                
            default_pwd_b64 = user_config.get("default_ad_password_b64", "aGVzbG8xMjM=")
            
            # Vytvoření složky pro fotografie
            import unicodedata
            def simple_slugify(text):
                text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
                text = text.lower()
                text = re.sub(r'[^a-z0-9\s_]', '', text)
                text = re.sub(r'[\s_]+', '_', text).strip('_')
                return text
                
            folder_name = simple_slugify(scraped_ad["title"])
            local_ad_photos_dir = PHOTOS_DIR / folder_name
            local_ad_photos_dir.mkdir(parents=True, exist_ok=True)
            
            days_old_val = 0
            try:
                dt = datetime.strptime(scraped_ad["date_created"], "%Y-%m-%d")
                days_old_val = (datetime.today() - dt).days
            except Exception:
                pass
                
            # Založíme nový inzerát v SQLite listings
            listing_id = str(uuid.uuid4())
            new_listing = {
                "id": listing_id,
                "title": scraped_ad["title"],
                "description": "Automaticky importovaný inzerát z Bazoše. Doplňte prosím popis.",
                "price": scraped_ad["price"],
                "category": get_target_domain(scraped_ad["title"], scraped_ad["url"]),
                "condition": "Aktivní",
                "local_photos_dir": str(local_ad_photos_dir),
                "location": user_config.get("location", "Český Krumlov 381 01"),
                "notes": "Automatický import",
                "ad_password_b64": default_pwd_b64,
                "bookmarklet_uri": "",
                "days_old": days_old_val,
                "created_at": scraped_ad["date_created"],
                "target_bazos": 1,
                "target_aukro": 0
            }
            
            portal_item_id = extract_ad_id(scraped_ad["url"])
            bazos_state_data = {
                "portal_item_id": portal_item_id,
                "url": scraped_ad["url"],
                "status": "Aktivní",
                "views": scraped_ad["views"],
                "last_synced": datetime.now().isoformat()
            }
            
            save_listing(new_listing, {"bazos": bazos_state_data})
            
            result.append({
                "portal_item_id": portal_item_id,
                "title": scraped_ad["title"],
                "url": scraped_ad["url"],
                "views": scraped_ad["views"],
                "status": "Aktivní"
            })
            
        return result
