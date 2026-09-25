import re
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

STOP_WORDS = {
    "prodam", "nabizim", "koupim", "vymena", "vymenim", "top", "stav", 
    "zaruka", "dph", "odpocet", "odpoctem", "servis", "super", "krasny", 
    "nova", "novy", "nove", "auto", "osobni", "motor", "rok", "rv", 
    "cr", "cz", "original", "komplet", "velmi", "pekny", "topstav", "1majitel",
    "s", "se", "v", "ve", "k", "ke", "o", "na", "do", "po", "za", "ze", "z", "bez", "pod", "nad",
    "pojezd", "pojezdem", "kufru", "baleni"
}

def extract_search_keywords(title: str) -> str:
    """
    Extrahuje z titulku inzerátu nejvhodnější vyhledávací frázi (2-3 klíčová slova),
    kterou by potenciální kupec zadal do vyhledávače (např. 'VW Arteon' nebo 'Škoda Octavia').
    """
    if not title:
        return ""

    # Odstraníme oddělovače a speciální znaky
    clean = re.sub(r'[\/\\\|\(\)\[\]\{\}\*_\-\+:,]', ' ', title)
    words = clean.split()

    filtered = []
    for w in words:
        w_lower = w.lower().strip()
        # Odstranit tečky a čárky z okrajů
        w_clean = re.sub(r'^[^\w]+|[^\w]+$', '', w_lower)
        if not w_clean:
            continue
        # Přeskočit stop-slova
        if w_clean in STOP_WORDS:
            continue
        # Přeskočit čistě technické specifikace výkonu/paliva jako 206kw, 110kw, 2.0tdi pokud už máme značku a model
        if re.match(r'^\d+(\.\d+)?[a-z]*$', w_clean) and len(filtered) >= 2:
            continue
        if w_clean in ("tdi", "tsi", "dsg", "4m", "4motion", "4x4", "quattro") and len(filtered) >= 2:
            continue

        filtered.append(w)
        if len(filtered) >= 3:
            # Maximálně 3 klíčová slova (Značka + Model + Varianta)
            break

    if not filtered:
        # Fallback na první 2 původní slova
        filtered = words[:2]

    return " ".join(filtered)

def _parse_total_results(html: str) -> Optional[int]:
    """Vyparsuje celkový počet inzerátů ze stránky výsledků Bazoše."""
    if not html:
        return None
    count_match = re.search(r'inzerátů z\s*(\d+)', html, re.I)
    if count_match:
        return int(count_match.group(1))
    return None

def check_bazos_search_rank(
    portal_item_id: str, 
    title: str, 
    subdomain: str = "auto.bazos.cz", 
    query: Optional[str] = None, 
    max_pages: int = 5
) -> Dict[str, Any]:
    """
    Vyhledá inzerát na Bazoši podle vyhledávacího dotazu a zjistí jeho přesnou pozici (rank) a stránku.
    Prohledává až `max_pages` stránek (výchozí 5 stránek = až 100 inzerátů).
    """
    search_query = query.strip() if query else extract_search_keywords(title)
    if not search_query:
        search_query = title[:20].strip()

    result = {
        "found": False,
        "rank_position": None,
        "rank_page": None,
        "query": search_query,
        "is_top": False,
        "total_results": None,
        "checked_at": datetime.now().isoformat()
    }

    if not portal_item_id:
        return result

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }

    item_id_str = str(portal_item_id).strip()
    encoded_query = urllib.parse.quote(search_query)

    for page_idx in range(0, max_pages * 20, 20):
        page_num = (page_idx // 20) + 1
        if page_idx == 0:
            url = f"https://{subdomain}/?hledat={encoded_query}&hlokalita=&humkreis=25&cenaod=&cenado=&Submit=Hledat"
        else:
            url = f"https://{subdomain}/{page_idx}/?hledat={encoded_query}&hlokalita=&humkreis=25&cenaod=&cenado=&Submit=Hledat"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            break

        soup = BeautifulSoup(html, "html.parser")
        ad_elements = soup.find_all(class_=re.compile(r"\binzeraty\b"))
        if not ad_elements:
            break

        # Pokus o zjištění celkového počtu nalezených inzerátů na 1. stránce
        if page_idx == 0:
            result["total_results"] = _parse_total_results(html)

        for idx_on_page, ad_el in enumerate(ad_elements):
            ad_html = str(ad_el)
            # Ověříme přítomnost ID v odkazu nebo v parametru akce
            if (f"/inzerat/{item_id_str}/" in ad_html or 
                f"'{item_id_str}'" in ad_html or 
                f'"{item_id_str}"' in ad_html or
                item_id_str in ad_html):
                
                overall_rank = page_idx + idx_on_page + 1
                is_top = bool(ad_el.find(class_="ztop"))

                result["found"] = True
                result["rank_position"] = overall_rank
                result["rank_page"] = page_num
                result["is_top"] = is_top
                return result

    return result
