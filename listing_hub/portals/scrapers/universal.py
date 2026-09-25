"""
Univerzální modul pro extrakci statistik a počtu zhlédnutí z veřejných inzertních webů.

Implementuje 3úrovňovou detekční pipeline:
1. Doménově specifické extraktory (Bazoš, Sbazar, Aukro, Vinted, Facebook, Sportovní vozy, Ráj veteránů, Motorkáři atd.)
2. Strukturovaná metadata (Schema.org / JSON-LD / OpenGraph)
3. Univerzální heuristický regex engine pro české a anglické inzertní weby
"""

import re
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8"
}

# --- Úroveň 1: Doménově specifické extraktory ---

def _extract_domain_specific(url: str, html: str) -> Optional[int]:
    """Zkusí extrahovat zhlédnutí podle známých doménových selektorů a datových struktur."""
    parsed_url = urllib.parse.urlparse(url.lower())
    netloc = parsed_url.netloc

    # 1.1 Bazoš.cz / Bazoš.sk
    if "bazos.cz" in netloc or "bazos.sk" in netloc:
        match = re.search(r"Vidělo:\s*<strong>?(\d+)", html, re.I)
        if match:
            return int(match.group(1))
        match_sk = re.search(r"Videlo:\s*<strong>?(\d+)", html, re.I)
        if match_sk:
            return int(match_sk.group(1))

    # 1.2 Sbazar.cz
    if "sbazar.cz" in netloc:
        match = re.search(r'"viewsCount":\s*(\d+)', html)
        if match:
            return int(match.group(1))
        match2 = re.search(r'"view_count":\s*(\d+)', html)
        if match2:
            return int(match2.group(1))
        match3 = re.search(r"(?:Zobrazeno|Zhlédnuto|počet zobrazení|Vidělo)[:\s]*<strong>?(\d+)", html, re.I)
        if match3:
            return int(match3.group(1))

    # 1.3 Aukro.cz
    if "aukro.cz" in netloc:
        match = re.search(r'"viewsCount":\s*(\d+)', html)
        if match:
            return int(match.group(1))
        match2 = re.search(r'"views":\s*(\d+)', html)
        if match2:
            return int(match2.group(1))
        match3 = re.search(r'(\d+)\s*(?:zobrazení|zhlédnutí)', html, re.I)
        if match3:
            return int(match3.group(1))

    # 1.4 Vinted.cz / Vinted.com
    if "vinted.cz" in netloc or "vinted.com" in netloc or "vinted" in netloc:
        match = re.search(r'"view_count":\s*(\d+)', html)
        if match:
            return int(match.group(1))
        match2 = re.search(r'"views_count":\s*(\d+)', html)
        if match2:
            return int(match2.group(1))

    # 1.5 Sportovní vozy & Ráj veteránů
    if "sportovnivozy.cz" in netloc or "rajveteranu.cz" in netloc or "rajaut.cz" in netloc:
        match = re.search(r"Počet zobrazení detailu:\s*<strong>(\d+)x?</strong>", html, re.I)
        if match:
            return int(match.group(1))
        fallback_match = re.search(r"(\d+)\s*x?</strong></span></span></p>", html, re.I)
        if fallback_match:
            return int(fallback_match.group(1))

    # 1.6 Motorkáři.cz
    if "motorkari.cz" in netloc:
        match = re.search(r"(?:Zobrazeno|Zhlédnuto)[:\s]*<strong>?(\d+)", html, re.I)
        if match:
            return int(match.group(1))

    return None


# --- Úroveň 2: Strukturovaná metadata (Schema.org / JSON-LD) ---

def _extract_json_ld(html: str) -> Optional[int]:
    """Vyhledá JSON-LD strukturovaná data s počtem interakcí nebo zhlédnutí."""
    scripts = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.DOTALL)
    for script_content in scripts:
        try:
            data = json.loads(script_content.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Hledáme interactionStatistic
                stats = item.get("interactionStatistic")
                if isinstance(stats, dict):
                    count = stats.get("userInteractionCount")
                    if count is not None and str(count).isdigit():
                        return int(count)
                elif isinstance(stats, list):
                    for s in stats:
                        if isinstance(s, dict):
                            count = s.get("userInteractionCount")
                            if count is not None and str(count).isdigit():
                                return int(count)
                # Přímá pole
                for key in ("viewCount", "viewsCount", "interactionCount", "views"):
                    val = item.get(key)
                    if val is not None and str(val).isdigit():
                        return int(val)
        except Exception:
            continue
    return None


# --- Úroveň 3: Univerzální heuristický regex engine ---

_TAG = r"(?:<[^>]+>|\s)*"

HEURISTIC_PATTERNS = [
    # "Počet zobrazení: 123" nebo "Zhlédnuto: 456x" nebo "Zobrazeno: <strong>789</strong>"
    re.compile(r"(?:počet zobrazení|počet shlédnutí|zobrazeno|zhlédnuto|shlédnuto|vidělo|videlo)[:\s]+" + _TAG + r"(\d+[\d\s\.,]*)(?:\s*(?:x|krát))?" + _TAG, re.I),
    # "123x zobrazeno" nebo "456 zhlédnutí"
    re.compile(_TAG + r"(\d+[\d\s\.,]*)" + _TAG + r"(?:x|krát)?\s*(?:zobrazení|zobrazeno|zhlédnutí|shlédnutí|viděno|zobrazeni)", re.I),
    # Anglické varianty: "Views: 567" nebo "1,234 views"
    re.compile(r"(?:views|impressions|pageviews)[:\s]+" + _TAG + r"(\d+[\d\s\.,]*)(?:\s*x)?" + _TAG, re.I),
    re.compile(_TAG + r"(\d+[\d\s\.,]*)" + _TAG + r"(?:views|impressions|pageviews)", re.I)
]

def _parse_digits_with_separators(raw_str: str) -> Optional[int]:
    """Převede číslo s možnými oddělovači tisíců (mezera, tečka, čárka) na integer."""
    if not raw_str:
        return None
    cleaned = re.sub(r'[^\d]', '', raw_str)
    if cleaned and cleaned.isdigit():
        return int(cleaned)
    return None

def _extract_heuristic(html: str) -> Optional[int]:
    """Prohledá HTML text pomocí obecných heuristických regexů."""
    for pattern in HEURISTIC_PATTERNS:
        match = pattern.search(html)
        if match:
            val = _parse_digits_with_separators(match.group(1))
            if val is not None and 0 <= val <= 10_000_000:
                return val
    return None


def parse_views_from_html(url: str, html: str) -> Optional[int]:
    """
    Sjednocený 3úrovňový parser HTML obsahu.
    Umožňuje přímé testování bez provádění síťových volání.
    """
    if not html:
        return None

    # Úroveň 1: Doménově specifické extraktory
    views = _extract_domain_specific(url, html)
    if views is not None:
        return views

    # Úroveň 2: JSON-LD strukturovaná metadata
    views = _extract_json_ld(html)
    if views is not None:
        return views

    # Úroveň 3: Univerzální heuristický regex
    views = _extract_heuristic(html)
    if views is not None:
        return views

    return None


def scrape_listing_views(url: str, timeout: float = 4.0) -> Optional[int]:
    """
    Stáhne veřejné HTML zadané URL a extrahuje z něj počet zhlédnutí.
    Bezpečné: zachytává veškeré síťové a parsovací výjimky a vrací None.
    """
    if not url or not url.strip().startswith(("http://", "https://")):
        return None

    try:
        req = urllib.request.Request(url.strip(), headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Kontrola Content-Type – stahujeme pouze HTML/text
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and "text/html" not in content_type and "application/xhtml" not in content_type:
                logger.debug(f"Přeskakuji nepodporovaný Content-Type: {content_type} pro {url}")
                return None

            # Omezení velikosti stahovaného obsahu na max 500 KB
            raw_data = response.read(512 * 1024)
            html = raw_data.decode("utf-8", errors="ignore")
            return parse_views_from_html(url, html)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as net_err:
        logger.debug(f"Chyba sítě při scrapování {url}: {net_err}")
        return None
    except Exception as e:
        logger.debug(f"Neočekávaná chyba při scrapování {url}: {e}")
        return None
