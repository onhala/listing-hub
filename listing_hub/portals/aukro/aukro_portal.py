from typing import List, Dict, Any, Optional, Set
import re
import json
import uuid
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

from listing_hub.portals.base import AbstractPortal
from listing_hub.core import db
from listing_hub.core.config import PHOTOS_DIR


def _simple_slugify(text: str) -> str:
    """Převede název na bezpečný název složky pro fotografie."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s_]', '', text)
    text = re.sub(r'[\s_]+', '_', text).strip('_')
    return text


def _extract_keywords(txt: str) -> Set[str]:
    """Extrahuje významová klíčová slova bez diakritiky a stop-slov pro fuzzy párování inzerátů."""
    norm = unicodedata.normalize('NFKD', txt).encode('ascii', 'ignore').decode('utf-8').lower()
    words = re.findall(r'[a-z0-9]{3,}', norm)
    stop = {'pro', 'pod', 'nad', 'bez', 'nebo', 'prodam', 'nabizim', 'top', 'stav', 'nova', 'novy', 'osob', 'aukro'}
    return set(w for w in words if w not in stop)


class AukroPortal(AbstractPortal):
    """
    Integrace Aukro.cz prostřednictvím veřejného SSR profilu a REST API (backend-web/api).
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
        - https://aukro.cz/zapalovac-technoexport-bratislava-diplomat-7082098064
        - https://aukro.cz/vintage-hodinky-prim-7023849102
        - https://aukro.cz/nabidka/7023849102
        """
        if not url:
            return None
        clean_url = url.split("?")[0].rstrip("/")
        m = re.search(r'(?:-(\d{9,12})|\/(\d{9,12}))$', clean_url)
        if m:
            return m.group(1) or m.group(2)
        m2 = re.search(r'(\d{9,12})', clean_url)
        if m2:
            return m2.group(1)
        return None

    def fetch_user_active_listings(self, username: str) -> List[Dict[str, Any]]:
        """
        Stáhne veřejnou stránku aktivních nabídek prodejce https://aukro.cz/uzivatel/{username}/nabidky
        a extrahuje seznam položek z vloženého SSR aukCache (POST /backend-web/api/offers/searchItemsCommon).
        """
        if not username:
            return []

        clean_username = username.strip()
        if "/uzivatel/" in clean_username:
            m = re.search(r'/uzivatel/([^/?#]+)', clean_username)
            if m:
                clean_username = m.group(1)
        clean_username = clean_username.strip("/")

        url = f"https://aukro.cz/uzivatel/{clean_username}/nabidky"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "cs,en;q=0.9"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"  [Aukro Sync] Chyba při načítání nabídek uživatele {clean_username}: {e}")
            return []

        # Parsování aukCache z HTML
        items = []
        for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL):
            s = m.group(1).strip()
            if "aukCache" in s and "searchItemsCommon" in s:
                try:
                    data = json.loads(s)
                    for k, v in data.get("aukCache", {}).items():
                        if "searchItemsCommon" in k and isinstance(v, dict):
                            body = v.get("b", {})
                            content = body.get("content", [])
                            if content:
                                items.extend(content)
                except Exception as parse_err:
                    print(f"  [Aukro Sync] Chyba při parsování aukCache: {parse_err}")

        # Normalizace nalezených položek
        results = []
        seen_ids = set()
        for it in items:
            item_id = str(it.get("itemId", ""))
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            seo_url = it.get("seoUrl", "")
            full_url = f"https://aukro.cz/{seo_url}-{item_id}" if seo_url else f"https://aukro.cz/nabidka/{item_id}"

            price_val = 0
            if it.get("price") and isinstance(it["price"], dict) and it["price"].get("amount"):
                price_val = it["price"].get("amount", 0)
            elif it.get("buyNowPrice") and isinstance(it["buyNowPrice"], dict) and it["buyNowPrice"].get("amount"):
                price_val = it["buyNowPrice"].get("amount", 0)

            results.append({
                "item_id": item_id,
                "title": (it.get("itemName") or "Aukro položka").strip(),
                "url": full_url,
                "price": int(price_val or 0),
                "starting_time": it.get("startingTime", ""),
                "ending_time": it.get("endingTime", ""),
                "item_state": it.get("itemState", "ACTIVE"),
                "title_image_url": it.get("titleImageUrl", ""),
                "location": it.get("location", ""),
                "postcode": it.get("postcode", ""),
                "watchers": it.get("watchersCount", 0),
                "is_auction": it.get("auction", False)
            })

        return results

    def fetch_offer_detail(self, item_id: str) -> Dict[str, Any]:
        """
        Stáhne detail nabídky z Aukro REST API nebo detail stránky.
        Vrací slovník s views (displayedCount), watchers, description, ending_time, images atd.
        """
        result = {
            "views": 0,
            "watchers": 0,
            "bidders": 0,
            "bidders_count": 0,
            "item_type": "BUY_NOW",
            "ending_time_text": "",
            "next_bid_min": None,
            "bargaining_available": False,
            "shipping_options": [],
            "seller": {},
            "description": "",
            "ending_time": None,
            "images": [],
            "state": "ACTIVE"
        }
        if not item_id:
            return result

        api_url = f"https://aukro.cz/backend-web/api/offers/{item_id}/offerDetail?pageType=DETAIL&requestedFor="
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "X-Accept-Subbrand": "BAZAAR"
        }

        def _parse_payload(data: dict):
            result["views"] = int(data.get("displayedCount") or 0)
            result["watchers"] = int(data.get("watchingUserCount") or 0)
            bidders = int(data.get("biddersCount") or 0)
            result["bidders"] = bidders
            result["bidders_count"] = bidders
            result["item_type"] = data.get("itemType") or ("BIDDING" if data.get("biddersCount") is not None and not data.get("buyNowActive") else "BUY_NOW")
            result["ending_time_text"] = (data.get("endingTimeText") or "").strip()
            result["bargaining_available"] = bool(data.get("bargainingAvailable") or data.get("bestOfferEnabled"))

            if data.get("nextBidMinAmount") and isinstance(data["nextBidMinAmount"], dict):
                result["next_bid_min"] = data["nextBidMinAmount"].get("amount")

            # Parse shipping
            shipping_opts = []
            for opt in data.get("shippingOptions", []):
                p_amt = 0
                if opt.get("firstPackagePrice") and isinstance(opt["firstPackagePrice"], dict):
                    p_amt = opt["firstPackagePrice"].get("amount", 0)
                elif opt.get("freeOfCharge"):
                    p_amt = 0
                shipping_opts.append({
                    "price": int(p_amt),
                    "free": bool(opt.get("freeOfCharge")),
                    "aukro_shipping": bool(opt.get("aukroShipping")),
                    "icon": opt.get("iconUrl") or ""
                })
            result["shipping_options"] = shipping_opts

            if data.get("seller") and isinstance(data["seller"], dict):
                s = data["seller"]
                result["seller"] = {
                    "rating": s.get("rating"),
                    "positive_percentage": s.get("positiveFeedbackPercentage"),
                    "feedback_count": s.get("feedbackUniqueUserCount")
                }

            result["description"] = (data.get("descriptionStripped") or data.get("descriptionInHtml") or "").strip()
            result["ending_time"] = data.get("endingTime")
            result["state"] = data.get("state", "ACTIVE")

            p_val = 0
            if data.get("price") and isinstance(data["price"], dict) and data["price"].get("amount"):
                p_val = data["price"].get("amount", 0)
            elif data.get("buyNowPrice") and isinstance(data["buyNowPrice"], dict) and data["buyNowPrice"].get("amount"):
                p_val = data["buyNowPrice"].get("amount", 0)
            result["price"] = int(p_val or 0)

            img_urls = []
            for img_obj in data.get("itemImages", []):
                sizes = img_obj.get("sizes", {})
                img_url = (sizes.get("ORIGINAL", {}).get("url") or
                           sizes.get("LARGE", {}).get("url") or
                           sizes.get("MEDIUM", {}).get("url"))
                if img_url:
                    img_urls.append(img_url)
            result["images"] = img_urls

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                _parse_payload(data)
                return result
        except Exception:
            try:
                page_url = f"https://aukro.cz/nabidka/{item_id}"
                req = urllib.request.Request(page_url, headers={"User-Agent": headers["User-Agent"]})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")

                for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL):
                    s = m.group(1).strip()
                    if "aukCache" in s and "offerDetail" in s:
                        data = json.loads(s)
                        for k, v in data.get("aukCache", {}).items():
                            if "offerDetail" in k and isinstance(v, dict):
                                body = v.get("b", {})
                                _parse_payload(body)
                                return result
            except Exception:
                pass

        return result

    def fetch_ad_details(self, url: str) -> Dict[str, Any]:
        """
        Ověří dostupnost a stav konkrétního inzerátu na Aukru z jeho URL.
        Využívá se při obnovení stavu z karty inzerátu (btn-refresh-portal-status).
        """
        result: Dict[str, Any] = {
            "status": "Nenalezeno",
            "is_active": False,
            "title": None,
            "price": None,
            "views": None,
            "error": None
        }
        item_id = self.extract_item_id_from_url(url)
        if not item_id:
            result["error"] = "Neplatná Aukro URL"
            return result

        detail = self.fetch_offer_detail(item_id)
        if detail and (detail.get("views") is not None or detail.get("description")):
            is_active = (detail.get("state") == "ACTIVE")
            result["is_active"] = is_active
            result["status"] = "Aktivní" if is_active else "Ukončeno"
            result["views"] = detail.get("views")
            result["price"] = detail.get("price")
            result["watchers"] = detail.get("watchers")
            result["ending_time"] = detail.get("ending_time")
            result["ending_time_text"] = detail.get("ending_time_text")
            result["item_type"] = detail.get("item_type")
            result["bidders_count"] = detail.get("bidders_count")
            result["next_bid_min"] = detail.get("next_bid_min")
            result["bargaining_available"] = detail.get("bargaining_available")
            result["shipping_options"] = detail.get("shipping_options")
        return result

    def download_photos_if_missing(self, image_urls: List[str], local_photos_dir_str: str) -> None:
        """Stáhne fotografie nabídky z Aukro CDN do lokální složky, pokud je prázdná."""
        if not local_photos_dir_str or not image_urls:
            return
        try:
            p_dir = Path(local_photos_dir_str)
            p_dir.mkdir(parents=True, exist_ok=True)
            existing_files = list(p_dir.glob("*.jpg")) + list(p_dir.glob("*.jpeg")) + list(p_dir.glob("*.png"))
            if len(existing_files) > 0:
                return

            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            for idx, img_url in enumerate(image_urls, start=1):
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
        """
        Synchronizuje aktivní nabídky z Aukra do Listing Hubu:
        1. Načte položky prodejce (podle user_config['aukro_username']).
        2. Spáruje se stávajícími inzeráty v SQLite (podle Aukro ID, URL, nebo názvu).
        3. Aktualizuje ceny, zhlédnutí, počty sledujících a stav.
        4. Pokud inzerát v SQLite neexistuje, automaticky jej importuje včetně popisu a fotek.
        5. Inzeráty dříve aktivní na Aukru, které už nejsou v nabídce, označí jako Ukončeno.
        """
        username = (user_config.get("aukro_username") or "").strip()
        if not username:
            print("  [Aukro Sync] Přeskočeno – v konfiguraci není zadáno 'aukro_username'.")
            return []

        print(f"  [Aukro Sync] Stahuji aktivní nabídky pro prodejce '{username}'...")
        scraped_items = self.fetch_user_active_listings(username)
        print(f"  [Aukro Sync] Nalezeno {len(scraped_items)} aktivních nabídek na Aukru.")

        local_listings = db.get_all_listings()
        matched_scraped_indices = set()
        result = []

        # 1. Projdeme lokální inzeráty a spárujeme je
        for local_ad in local_listings:
            aukro_state = local_ad.get("portal_states", {}).get("aukro", {})
            local_url = (aukro_state.get("url") or "").strip()
            local_item_id = aukro_state.get("portal_item_id") or self.extract_item_id_from_url(local_url)

            best_match = None
            best_idx = -1

            # Priority 1: Match dle Aukro item_id
            if local_item_id:
                for idx, sc_item in enumerate(scraped_items):
                    if idx in matched_scraped_indices:
                        continue
                    if sc_item["item_id"] == str(local_item_id):
                        best_match = sc_item
                        best_idx = idx
                        break

            # Priority 2: Match dle URL
            if not best_match and local_url:
                for idx, sc_item in enumerate(scraped_items):
                    if idx in matched_scraped_indices:
                        continue
                    if sc_item["url"].strip() == local_url:
                        best_match = sc_item
                        best_idx = idx
                        break

            # Priority 3: Match dle normalizovaného nadpisu
            if not best_match and local_ad.get("title"):
                local_title_norm = re.sub(r'\s+', ' ', local_ad["title"][:50].lower().strip())
                for idx, sc_item in enumerate(scraped_items):
                    if idx in matched_scraped_indices:
                        continue
                    sc_title_norm = re.sub(r'\s+', ' ', sc_item["title"][:50].lower().strip())
                    if sc_title_norm == local_title_norm and len(local_title_norm) > 3:
                        best_match = sc_item
                        best_idx = idx
                        break

            # Priority 4: Fuzzy match dle klíčových slov
            if not best_match and local_ad.get("title"):
                l_kw = _extract_keywords(local_ad["title"])
                if l_kw:
                    best_kw_ratio = 0.0
                    for idx, sc_item in enumerate(scraped_items):
                        if idx in matched_scraped_indices:
                            continue
                        s_kw = _extract_keywords(sc_item["title"])
                        if not s_kw:
                            continue
                        common = l_kw & s_kw
                        ratio = len(common) / min(len(l_kw), len(s_kw))
                        if len(common) >= 2 and ratio >= 0.6 and ratio > best_kw_ratio:
                            best_kw_ratio = ratio
                            best_match = sc_item
                            best_idx = idx

            if best_match:
                matched_scraped_indices.add(best_idx)
                item_id = best_match["item_id"]

                # Stáhneme živý detail pro views a watchers
                detail = self.fetch_offer_detail(item_id)
                views_count = detail.get("views", 0)
                watchers_count = detail.get("watchers") if detail.get("watchers") is not None else best_match.get("watchers", 0)

                # Aktualizujeme lokální záznam
                local_ad["target_aukro"] = 1
                if best_match.get("price"):
                    local_ad["price"] = best_match["price"]
                elif detail.get("price"):
                    local_ad["price"] = detail["price"]

                if not local_ad.get("description") and detail.get("description"):
                    local_ad["description"] = detail["description"]

                bidders_count = detail.get("bidders_count", 0)
                item_type = detail.get("item_type") or ("BIDDING" if best_match.get("is_auction") else "BUY_NOW")
                ending_time_text = detail.get("ending_time_text") or ""

                top_info_parts = []
                if item_type == "BIDDING":
                    top_info_parts.append(f"{bidders_count} příh.")
                if watchers_count:
                    top_info_parts.append(f"sleduje {watchers_count}")
                top_info_str = " · ".join(top_info_parts)

                aukro_state_data = {
                    "portal_item_id": item_id,
                    "url": best_match["url"],
                    "status": "Aktivní",
                    "views": views_count,
                    "last_synced": datetime.now().isoformat(),
                    "top_expires_at": detail.get("ending_time") or best_match.get("ending_time"),
                    "top_info": top_info_str,
                    "portal_label": "Aukro.cz",
                    "item_type": item_type,
                    "bidders_count": bidders_count,
                    "next_bid_min": detail.get("next_bid_min"),
                    "ending_time_text": ending_time_text,
                    "bargaining_available": detail.get("bargaining_available", False),
                    "shipping_options": detail.get("shipping_options", [])
                }

                db.save_listing(local_ad, {"aukro": aukro_state_data})
                if local_ad.get("id"):
                    db.record_views_snapshot(local_ad["id"], "aukro", views_count)

                # Stáhnout fotky pokud chybí
                if detail.get("images") and local_ad.get("local_photos_dir"):
                    self.download_photos_if_missing(detail["images"], local_ad["local_photos_dir"])

                result.append({
                    "portal_item_id": item_id,
                    "title": local_ad.get("title"),
                    "url": best_match["url"],
                    "views": views_count,
                    "watchers": watchers_count,
                    "status": "Aktivní",
                    "is_new": False
                })
            else:
                # Inzerát má stav Aukro 'Aktivní', ale už není v nabídce -> Expiroval / Ukončeno
                if aukro_state and aukro_state.get("status") == "Aktivní":
                    aukro_state["status"] = "Ukončeno"
                    aukro_state["last_synced"] = datetime.now().isoformat()
                    db.save_listing(local_ad, {"aukro": aukro_state})

        # 2. Nově nalezené inzeráty z Aukra, které ještě nemáme v SQLite
        for idx, sc_item in enumerate(scraped_items):
            if idx in matched_scraped_indices:
                continue

            item_id = sc_item["item_id"]
            print(f"  [Aukro Sync] Importuji novou položku z Aukra: {sc_item['title']} ({item_id})")

            # Stáhneme plný detail
            detail = self.fetch_offer_detail(item_id)
            views_count = detail.get("views", 0)
            watchers_count = detail.get("watchers") if detail.get("watchers") is not None else sc_item.get("watchers", 0)

            # Složka pro fotografie
            slug = _simple_slugify(sc_item["title"][:30]) or "aukro_ad"
            local_ad_photos_dir = PHOTOS_DIR / f"{slug}_{item_id}"

            # Stáhneme fotografie
            images_to_download = detail.get("images") or ([sc_item["title_image_url"]] if sc_item.get("title_image_url") else [])
            self.download_photos_if_missing(images_to_download, str(local_ad_photos_dir))

            # Spočítáme stáří
            days_old_val = 0
            created_at_val = datetime.now().strftime("%Y-%m-%d")
            if sc_item.get("starting_time"):
                try:
                    st_str = sc_item["starting_time"][:10]
                    dt = datetime.strptime(st_str, "%Y-%m-%d")
                    days_old_val = max(0, (datetime.today() - dt).days)
                    created_at_val = st_str
                except Exception:
                    pass

            desc_text = detail.get("description") or f"Položka importovaná z Aukro.cz: {sc_item['title']}"
            loc_text = sc_item.get("location") or user_config.get("location", "Český Krumlov")
            if sc_item.get("postcode"):
                loc_text = f"{loc_text} {sc_item['postcode']}".strip()

            listing_id = str(uuid.uuid4())
            new_listing = {
                "id": listing_id,
                "title": sc_item["title"],
                "description": desc_text,
                "price": sc_item["price"],
                "category": "Aukro",
                "condition": "Aktivní",
                "local_photos_dir": str(local_ad_photos_dir),
                "location": loc_text,
                "notes": f"Importováno z Aukro.cz (ID {item_id})",
                "ad_password_b64": user_config.get("default_ad_password_b64", ""),
                "bookmarklet_uri": "",
                "days_old": days_old_val,
                "created_at": created_at_val,
                "target_bazos": 0,
                "target_aukro": 1
            }

            bidders_count = detail.get("bidders_count", 0)
            item_type = detail.get("item_type") or ("BIDDING" if sc_item.get("is_auction") else "BUY_NOW")
            ending_time_text = detail.get("ending_time_text") or ""

            top_info_parts = []
            if item_type == "BIDDING":
                top_info_parts.append(f"{bidders_count} příh.")
            if watchers_count:
                top_info_parts.append(f"sleduje {watchers_count}")
            top_info_str = " · ".join(top_info_parts)

            aukro_state_data = {
                "portal_item_id": item_id,
                "url": sc_item["url"],
                "status": "Aktivní",
                "views": views_count,
                "last_synced": datetime.now().isoformat(),
                "top_expires_at": detail.get("ending_time") or sc_item.get("ending_time"),
                "top_info": top_info_str,
                "portal_label": "Aukro.cz",
                "item_type": item_type,
                "bidders_count": bidders_count,
                "next_bid_min": detail.get("next_bid_min"),
                "ending_time_text": ending_time_text,
                "bargaining_available": detail.get("bargaining_available", False),
                "shipping_options": detail.get("shipping_options", [])
            }

            db.save_listing(new_listing, {"aukro": aukro_state_data})
            db.record_views_snapshot(listing_id, "aukro", views_count)

            result.append({
                "portal_item_id": item_id,
                "title": sc_item["title"],
                "url": sc_item["url"],
                "views": views_count,
                "watchers": watchers_count,
                "status": "Aktivní",
                "is_new": True
            })

        return result

    def fetch_seller_profile(self, username: str) -> Dict[str, Any]:
        """
        Stáhne reputaci a statistiky prodejce z veřejného profilu Aukra.
        Vrací např.: {"rating": 156, "positive_percentage": 0.9937, "feedback_count": 157}
        """
        res = {
            "username": username,
            "rating": None,
            "positive_percentage": None,
            "feedback_count": None,
            "aukro_plus": False,
            "success": False
        }
        if not username:
            return res

        profile_url = f"https://aukro.cz/uzivatel/{username}/nabidky"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            req = urllib.request.Request(profile_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL):
                s = m.group(1).strip()
                if "aukCache" in s and "seller" in s:
                    data = json.loads(s)
                    for k, v in data.get("aukCache", {}).items():
                        if isinstance(v, dict) and "b" in v and isinstance(v["b"], dict):
                            b = v["b"]
                            seller_data = b.get("seller") or (b.get("list") and b["list"][0].get("seller") if b.get("list") else None)
                            if seller_data and isinstance(seller_data, dict):
                                res["rating"] = seller_data.get("rating")
                                res["positive_percentage"] = seller_data.get("positiveFeedbackPercentage")
                                res["feedback_count"] = seller_data.get("feedbackUniqueUserCount")
                                res["aukro_plus"] = bool(seller_data.get("aukroPlus"))
                                res["success"] = True
                                return res
        except Exception as e:
            res["error"] = str(e)
        return res

