"""
listing_hub.portals.sauto.sauto_portal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integrace a podpora auto-moto inzertního portálu Sauto.cz (Seznam.cz).
Zajišťuje parsování Sauto URL, detekci stavu (Aktivní vs. Expirováno/Smazáno),
extrakci ceny, zhlédnutí a kontrolu platnosti inzerátu (Expiration Sentinel).
"""

import re
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import List, Dict, Any, Optional
from listing_hub.portals.base import AbstractPortal

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8"
}


class SautoPortal(AbstractPortal):
    """
    Integrace inzertního portálu Sauto.cz.
    """

    @property
    def name(self) -> str:
        return "sauto"

    @property
    def display_name(self) -> str:
        return "Sauto.cz"

    @property
    def supported_domains(self) -> List[str]:
        return ["sauto.cz", "www.sauto.cz"]

    def extract_item_id_from_url(self, url: str) -> Optional[str]:
        """
        Extrahuje ID inzerátu ze Sauto URL.
        Příklady:
        - https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491
        - https://www.sauto.cz/osobni/detail/volkswagen/arteon/20658491?campaign=...
        - https://sauto.cz/detail/20658491
        - https://www.sauto.cz/inzerat/20658491
        """
        if not url:
            return None
        clean_url = url.split("?")[0].split("#")[0].rstrip("/")
        # 1. Hledáme koncové číselné ID (např. .../arteon/20658491)
        m = re.search(r'/(\d{6,12})$', clean_url)
        if m:
            return m.group(1)
        # 2. Hledáme obecné číslo za /detail/ nebo /inzerat/
        m2 = re.search(r'/(?:detail|inzerat)(?:/[^/]+)*/(\d+)', clean_url)
        if m2:
            return m2.group(1)
        # 3. Jakékoliv souvislé číslo 7+ číslic v cestě
        m3 = re.search(r'/(\d{7,10})(?:/|$)', clean_url)
        if m3:
            return m3.group(1)
        return None

    def fetch_ad_details(self, url: str) -> Dict[str, Any]:
        """
        Ověří dostupnost a stav inzerátu na Sauto.cz.
        Vrací slovník:
        {
            "status": "Aktivní" | "Expirováno" | "Smazáno" | "Nenalezeno",
            "is_active": bool,
            "title": Optional[str],
            "price": Optional[int],
            "views": Optional[int],
            "error": Optional[str]
        }
        """
        result: Dict[str, Any] = {
            "status": "Nenalezeno",
            "is_active": False,
            "title": None,
            "price": None,
            "views": None,
            "error": None
        }

        if not url:
            result["error"] = "Chybí URL adresa inzerátu"
            return result

        try:
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                
                # Detekce neaktivního / smazaného inzerátu v HTML
                expired_patterns = [
                    r"inzerát\s+(?:byl\s+smazán|již\s+není\s+aktivní|vypršel|neexistuje)",
                    r"platnost\s+inzerátu\s+vypršela",
                    r"tento\s+inzerát\s+byl\s+odstraněn",
                    r"hledaný\s+inzerát\s+nebyl\s+nalezen"
                ]
                for pat in expired_patterns:
                    if re.search(pat, html, re.I):
                        result["status"] = "Expirováno"
                        result["is_active"] = False
                        return result

                # Inzerát je aktivní (HTTP 200 a žádná hláška o smazání)
                result["status"] = "Aktivní"
                result["is_active"] = True

                # Extrakce titulku z <title> nebo meta tagů
                title_match = re.search(r'<title>([^<]+)</title>', html, re.I)
                if title_match:
                    raw_title = title_match.group(1).split("|")[0].split("- Sauto.cz")[0].strip()
                    if raw_title:
                        result["title"] = raw_title

                # Extrakce ceny z JSON-LD nebo HTML
                price_match = re.search(r'"price":\s*"?(\d+)"?', html)
                if price_match:
                    try:
                        result["price"] = int(price_match.group(1))
                    except ValueError:
                        pass
                
                if not result["price"]:
                    html_price = re.search(r'(\d[\d\s]{2,8})\s*Kč', html)
                    if html_price:
                        clean_p = re.sub(r'\s+', '', html_price.group(1))
                        if clean_p.isdigit():
                            result["price"] = int(clean_p)

                # Extrakce zobrazení
                views_match = re.search(r'"viewsCount":\s*(\d+)', html) or re.search(r'"viewCount":\s*(\d+)', html)
                if views_match:
                    result["views"] = int(views_match.group(1))

        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                result["status"] = "Expirováno"
                result["is_active"] = False
            else:
                result["status"] = "Chyba"
                result["error"] = f"HTTP {e.code}"
        except Exception as e:
            logger.warning(f"Chyba při stahování stavu Sauto inzerátu {url}: {e}")
            result["status"] = "Neznámý"
            result["error"] = str(e)

        return result

    def scrape_views(self, url: str) -> Optional[int]:
        """Získá aktuální počet zhlédnutí inzerátu na Sauto.cz."""
        details = self.fetch_ad_details(url)
        return details.get("views")

    def post_listing(self, listing: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Odkaz pro vytvoření inzerátu na Sauto.cz.
        """
        return {
            "portal_item_id": listing.get("id", "sauto-draft"),
            "url": "https://www.sauto.cz/pridat-inzerat",
            "status": "Koncept (Sauto)"
        }

    def update_price(self, portal_item_id: str, new_price: int, url: str, user_config: Dict[str, Any]) -> bool:
        """Aktualizace ceny na Sauto.cz."""
        return True

    def delete_listing(self, portal_item_id: str, url: str, password_b64: str, user_config: Dict[str, Any]) -> bool:
        """Smazání inzerátu ze Sauto.cz."""
        return True

    def sync_listings(self, user_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Synchronizace inzerátů ze Sauto.cz."""
        return []
