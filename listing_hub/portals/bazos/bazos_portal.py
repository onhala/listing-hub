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
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
import post_to_bazos
from listing_hub.core.config import PROJECT_ROOT

def download_bazos_photos_if_missing(ad_url: str, local_photos_dir_str: str):
    """
    Stáhne fotky z Bazoše v plném rozlišení, pokud lokální složka neobsahuje žádné fotky.
    Pokud v lokální složce už fotky existují (uživatel je vytvořil/nahrál lokálně), 
    stahování se přeskočí a uživatelské fotky zůstanou 100% zachovány.
    """
    if not ad_url or not local_photos_dir_str:
        return
        
    m_id = re.search(r'/inzerat/(\d+)/', ad_url)
    if not m_id:
        return
    target_id = m_id.group(1)

    p_dir = Path(local_photos_dir_str)
    if not p_dir.is_absolute():
        p_dir = PROJECT_ROOT / p_dir

    p_dir.mkdir(parents=True, exist_ok=True)

    # Pokud ve složce už existují fotky, nic nestahujeme
    existing = [f for f in os.listdir(p_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    if existing:
        return

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        req = urllib.request.Request(ad_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        photo_urls = []
        seen = set()
        
        for img in soup.find_all('img'):
            src = img.get('src', '')
            m = re.search(r'/img/(\d+)t?/(\d+)/(' + target_id + r')\.jpg', src)
            if m:
                img_num, sub_folder, item_id = m.groups()
                if img_num not in seen:
                    seen.add(img_num)
                    domain = 'https://www.bazos.cz'
                    if src.startswith('http'):
                        domain = src.split('/img/')[0]
                    full_res = f'{domain}/img/{img_num}/{sub_folder}/{item_id}.jpg'
                    photo_urls.append((int(img_num), full_res))
                    
        photo_urls.sort(key=lambda x: x[0])
        
        for idx, (_, img_url) in enumerate(photo_urls, start=1):
            try:
                img_req = urllib.request.Request(img_url, headers=headers)
                with urllib.request.urlopen(img_req, timeout=10) as img_resp:
                    img_data = img_resp.read()
                    if img_data:
                        save_path = p_dir / f"foto_{idx}.jpg"
                        with open(save_path, "wb") as f:
                            f.write(img_data)
            except Exception:
                pass
    except Exception:
        pass


def fetch_bazos_ad_details(ad_url: str) -> dict:
    """
    Stáhne detail stránky inzerátu z Bazoše a vytáhne popis a lokaci.
    Vrátí dict s klíči 'description', 'location' a 'is_deleted'.
    """
    result = {"description": "", "location": "", "is_deleted": False}
    if not ad_url:
        return result
    try:
        # Sanitize malformed or protocol-relative URLs
        if ad_url.startswith("//"):
            ad_url = "https:" + ad_url
        if "www.bazos.cz//" in ad_url:
            ad_url = "https://" + ad_url.split("www.bazos.cz//")[-1]
            
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        req = urllib.request.Request(ad_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            final_url = resp.geturl()
            # Pokud dojde k přesměrování mimo detail inzerátu (např. na úvodní stránku nebo vyhledávání), ignorujeme
            if "/inzerat/" not in final_url:
                result["is_deleted"] = True
                return result
            html = resp.read().decode('utf-8', errors='ignore')

        # Pokud stránka obsahuje oznámení o smazání / vymazání inzerátu
        html_lower = html.lower()
        if 'vymazán' in html_lower or 'smazán' in html_lower or 'neexistuje' in html_lower or 'byl smazán' in html_lower:
            result["is_deleted"] = True
            return result

        soup = BeautifulSoup(html, 'html.parser')

        # --- Popis ---
        desc_el = soup.find(class_='popis')
        if not desc_el:
            desc_el = soup.find(attrs={'class': re.compile(r'popis', re.I)})
        if desc_el:
            result["description"] = desc_el.get_text(separator='\n', strip=True)

        # --- Lokace ---
        loc_el = soup.find(class_='inzeratylok')
        if not loc_el:
            loc_el = soup.find(attrs={'class': re.compile(r'lok|lokal|lokace', re.I)})
        if loc_el:
            loc_text = loc_el.get_text(separator=' ', strip=True)
            loc_text = re.sub(r'([^\d\s])(\d)', r'\1 \2', loc_text)
            loc_text = re.sub(r'\s+', ' ', loc_text).strip()
            if loc_text:
                result["location"] = loc_text

    except Exception:
        pass

    return result

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
        def _fetch_html_on_worker(page, cfg):
            page.goto("https://www.bazos.cz/moje-inzeraty.php")
            page.wait_for_timeout(1000)

            email_input = page.locator("input[name='mail']")
            phone_input = page.locator("input[name='telefon']")
            code_input = page.locator("input[name='kodd']")

            if email_input.is_visible(timeout=2000) is True:
                user_dict = cfg.get("user", cfg) if isinstance(cfg, dict) else {}
                email_val = str(user_dict.get("email") or (cfg.get("email") if isinstance(cfg, dict) else "") or "").strip()
                phone_val = str(user_dict.get("phone") or (cfg.get("phone") if isinstance(cfg, dict) else "") or "").strip()
                
                if not email_val or not phone_val or email_val == "tuj_email@example.com" or phone_val == "777123456":
                    raise Exception("V nastavení aplikace chybí tvůj reálný e-mail a telefon pro Bazoš.")
                
                email_input.fill(email_val)
                phone_input.fill(phone_val)
                
                list_btn = page.locator("input[type='submit'][value='Vypsat inzeráty']")
                if list_btn.is_visible(timeout=2000) is True:
                    list_btn.click()
                    page.wait_for_timeout(1500)

            # 2. Kontrola, zda Bazoš vyžaduje SMS kód
            try:
                page.wait_for_selector("input[name='kodd']", timeout=3000)
                # Pokud se pole pro SMS kód objeví, čekáme až 90s, než ho uživatel zadá v Živém prohlížeči
                page.wait_for_selector("input[name='kodd']", state="hidden", timeout=90000)
            except Exception:
                # SMS kód nebyl vyžadován (uživatel je přihlášen) nebo vypršel krátký 3s check
                pass

            # 3. Kontrola: Pokud na stránce stále zůstalo pole pro SMS kód (vypršel timeout 90s)
            if page.locator("input[name='kodd']").is_visible(timeout=1000) is True:
                raise Exception("Vypršel čas pro zadání SMS kódu. Zadej jej prosím v záložce Živý prohlížeč a zkus synchronizaci znovu.")

            # Uložíme platné session cookies pro příští rychlé přihlášení
            try:
                from listing_hub.core.config import SESSION_STATE_PATH
                page.context.storage_state(path=str(SESSION_STATE_PATH))
            except Exception:
                pass

            return page.content()

        try:
            html_content = session_manager.run_on_worker(_fetch_html_on_worker, user_config)
        except Exception as e:
            if "Bazoš" in str(e) or "nastavení" in str(e) or "SMS" in str(e):
                raise e
            raise Exception(f"Přihlášení k Bazoši selhalo: {e}")

        # Stáhneme inzeráty z HTML
        scraped_listings = scrape_listings_from_html(html_content)
        
        # Načteme lokální inzeráty z SQLite
        local_listings = get_all_listings()
        matched_scraped_indices = set()
        
        result = []
        
        # 1. Spárujeme stávající SQLite inzeráty a aktualizujeme je
        for local_ad in local_listings:
            bazos_state = local_ad.get("portal_states", {}).get("bazos", {})
            local_url = bazos_state.get("url", "").strip()
            local_ad_id = extract_ad_id(local_url)
            
            best_scraped_match = None
            best_scraped_idx = -1
            
            # Priority 1: Match podle Bazoš ID inzerátu (zaručuje 100% přináležitost)
            if local_ad_id:
                for s_idx, scraped_ad in enumerate(scraped_listings):
                    if s_idx in matched_scraped_indices:
                        continue
                    scraped_id = extract_ad_id(scraped_ad["url"])
                    if scraped_id and scraped_id == local_ad_id:
                        best_scraped_match = scraped_ad
                        best_scraped_idx = s_idx
                        break

            # Priority 2: Match podle přesné URL
            if not best_scraped_match and local_url:
                for s_idx, scraped_ad in enumerate(scraped_listings):
                    if s_idx in matched_scraped_indices:
                        continue
                    if scraped_ad["url"].strip() == local_url:
                        best_scraped_match = scraped_ad
                        best_scraped_idx = s_idx
                        break
                        
            # Priority 3: Match podle nadpisu (normalizovaný řetězec)
            if not best_scraped_match and local_ad.get("title"):
                local_title_clean = re.sub(r'\s+', ' ', local_ad["title"][:50].lower().strip())
                for s_idx, scraped_ad in enumerate(scraped_listings):
                    if s_idx in matched_scraped_indices:
                        continue
                    scraped_title_clean = re.sub(r'\s+', ' ', scraped_ad["title"][:50].lower().strip())
                    if scraped_title_clean == local_title_clean and len(local_title_clean) > 3:
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

                # Pokud má inzerát ještě placeholder popis, dofetchuj reálný z Bazoše
                _PLACEHOLDER = "Automaticky importovaný inzerát z Bazoše. Doplňte prosím popis."
                if local_ad.get("description", "").strip() == _PLACEHOLDER:
                    _details = fetch_bazos_ad_details(best_scraped_match["url"])
                    if _details["description"]:
                        local_ad["description"] = _details["description"]
                    if _details["location"]:
                        local_ad["location"] = _details["location"]
                
                bazos_state_data = {
                    "portal_item_id": portal_item_id,
                    "url": best_scraped_match["url"],
                    "status": "Aktivní",
                    "views": best_scraped_match["views"],
                    "last_synced": datetime.now().isoformat()
                }
                save_listing(local_ad, {"bazos": bazos_state_data})
                
                # Stáhnout fotky z Bazoše pouze pokud lokální složka neobsahuje žádné fotky
                download_bazos_photos_if_missing(best_scraped_match["url"], local_ad.get("local_photos_dir", ""))
                
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
                
            # Stáhnout detail inzerátu (popis, lokace) z Bazoše
            ad_details = fetch_bazos_ad_details(scraped_ad["url"])
            description_text = ad_details["description"] or "Automaticky importovaný inzerát z Bazoše. Doplňte prosím popis."
            location_text = ad_details["location"] or user_config.get("location", "Český Krumlov 381 01")

            # Založíme nový inzerát v SQLite listings
            listing_id = str(uuid.uuid4())
            new_listing = {
                "id": listing_id,
                "title": scraped_ad["title"],
                "description": description_text,
                "price": scraped_ad["price"],
                "category": get_target_domain(scraped_ad["title"], scraped_ad["url"]),
                "condition": "Aktivní",
                "local_photos_dir": str(local_ad_photos_dir),
                "location": location_text,
                "notes": "",
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
            
            # Stáhnout fotky z Bazoše pouze pokud lokální složka neobsahuje žádné fotky
            download_bazos_photos_if_missing(scraped_ad["url"], str(local_ad_photos_dir))
            
            result.append({
                "portal_item_id": portal_item_id,
                "title": scraped_ad["title"],
                "url": scraped_ad["url"],
                "views": scraped_ad["views"],
                "status": "Aktivní"
            })
            
        return result
