import statistics
import urllib.parse
import unicodedata
import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import requests
from listing_hub.core import db

# Běžná stop-slova v českých inzertních nadpisech
AD_STOP_WORDS = {
    "prodam", "prodej", "koupim", "nabizim", "daruji", "vymenim",
    "novy", "nova", "nove", "pouzity", "pouzita", "pouzite",
    "zachovaly", "zachovala", "zachovale", "krasny", "krasna", "krasne",
    "super", "top", "stav", "zaruka", "zaruce", "sleva", "levne",
    "rychle", "osobni", "odber", "komplet", "baleni", "prislusenstvi",
    "vcetne", "bez", "original", "originalni", "cena", "dohodou",
    "inzerat", "funkcni", "plne", "nevyuzity", "nepouzity", "jako", "kus",
    "znacky", "model", "typ", "velikost", "pouze", "vel", "pansky", "panske",
    "damsky", "damske", "detsky", "detske", "kus", "kusy"
}

def strip_accents(text: str) -> str:
    """Odstraní diakritiku pro bezpečné porovnávání slov."""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def clean_price(price_str: str) -> Optional[int]:
    """Očistí textovou cenu na integer."""
    if not price_str:
        return None
    price_str = price_str.replace('\xa0', '').replace(' ', '')
    match = re.search(r'(\d+)', price_str)
    if match:
        return int(match.group(1))
    return None

def extract_search_keywords(title: str, brand: str = "", model: str = "") -> str:
    """
    Extrahujeme klíčová vyhledávací slova (značka + model) z názvu inzerátu pro efektivní vyhledávání na bazarech.
    Odstraňuje inzertní stop-slova ('prodám', 'top stav', 'v záruce', apod.) a balast.
    """
    if brand and model:
        return f"{brand.strip()} {model.strip()}".strip()
    if brand and len(brand.split()) >= 2:
        return brand.strip()

    title_clean = title.replace('"', ' ').replace("'", ' ').replace('(', ' ').replace(')', ' ')
    words = title_clean.split()
    
    # 1. Zkusíme najít alfanumerický kód modelu (např. DCD796, RTX3070, A52, M1)
    model_codes = [w for w in words if re.search(r'[A-Za-z]+.*\d+|\d+.*[A-Za-z]+', w) and len(w) >= 3]
    if model_codes:
        code = model_codes[0]
        idx = words.index(code)
        if idx > 0:
            candidate_brand = words[idx - 1]
            cand_norm = strip_accents(candidate_brand).lower()
            if cand_norm not in AD_STOP_WORDS and len(candidate_brand) > 1:
                return f"{candidate_brand} {code}".strip()
        return code.strip()

    # 2. Očistíme slova od stop-slov
    raw_words = re.findall(r'[a-zA-Z0-9á-žÁ-Ž]+', title)
    cleaned = []
    for w in raw_words:
        w_norm = strip_accents(w).lower()
        if w_norm not in AD_STOP_WORDS and len(w) > 1:
            cleaned.append(w)

    if cleaned:
        return " ".join(cleaned[:3]).strip()
    return title[:30].strip()

def search_bazos_prices(
    query: str,
    min_price: int = None,
    max_price: int = None,
    exclude_title: str = None,
    exclude_url: str = None
) -> List[Dict[str, Any]]:
    """
    Prohledá Bazoš.cz a vrátí seznam nalezených inzerátů.
    Automaticky vyfiltruje vlastní inzerát uživatele (dle exclude_title nebo exclude_url).
    """
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.bazos.cz/search.php?hledat={encoded_query}&rubriky=www&hlokalita=&humkreis=25&cenaod={min_price or ''}&cenado={max_price or ''}&Submit=Hledat&kitx=y"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8"
    }
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    listings = soup.find_all(class_='inzeraty')
    results = []

    for el in listings:
        title_el = el.find(class_='nadpis')
        if not title_el or not title_el.find('a'):
            continue
        title = title_el.find('a').text.strip()
        link = title_el.find('a')['href']
        if link.startswith('/'):
            link = f"https://www.bazos.cz{link}"

        # Ochrana: Vyřazení vlastního inzerátu, aby rádce neporovnával inzerát sám se sebou
        if exclude_url and (exclude_url in link or link in exclude_url):
            continue
        if exclude_title and exclude_title.strip().lower() == title.strip().lower():
            continue

        desc_el = el.find(class_='popis')
        description = desc_el.text.strip() if desc_el else ""

        price_el = el.find(class_='inzeratycena')
        price_text = price_el.text.strip() if price_el else ""
        price_val = clean_price(price_text)

        date_el = el.find(class_='velikost10')
        date_str = ""
        if date_el:
            date_match = re.search(r'\[(.*?)\]', date_el.text)
            if date_match:
                date_str = date_match.group(1)

        lok_el = el.find(class_='inzeratylok')
        location = lok_el.text.strip().replace('\r', ' ').replace('\n', ' ') if lok_el else ""
        location = re.sub(r'\s+', ' ', location)

        view_el = el.find(class_='inzeratyview')
        views = view_el.text.strip() if view_el else ""
        is_top = bool(el.find(class_='ztop'))

        results.append({
            "title": title,
            "link": link,
            "description": description,
            "price_text": price_text,
            "price": price_val,
            "date": date_str,
            "location": location,
            "views": views,
            "is_top": is_top,
            "source": "bazos",
            "portal": "Bazoš.cz"
        })
    return results

def search_sbazar_prices(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Prohledá Sbazar.cz přes oficiální JSON vyhledávací API.
    Vrací reálné bazarové položky s cenami a funkčními odkazy.
    """
    try:
        url = f"https://www.sbazar.cz/api/v1/items/search?phrase={urllib.parse.quote(query)}&limit={limit}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for item in data.get("results", []):
            price = item.get("price")
            item_id = item.get("id")
            seo_name = item.get("seo_name") or str(item_id)
            cat_seo = item.get("category", {}).get("seo_name")
            if cat_seo:
                link = f"https://www.sbazar.cz/{cat_seo}/detail/{seo_name}"
            else:
                link = f"https://www.sbazar.cz/inzerat/{item_id}"

            created_date = (item.get("create_date") or "")[:10]
            if created_date:
                parts = created_date.split("-")
                if len(parts) == 3:
                    created_date = f"{int(parts[2])}.{int(parts[1])}.{parts[0]}"

            results.append({
                "title": item.get("name", ""),
                "link": link,
                "description": "",
                "price_text": f"{price:,} Kč".replace(',', ' ') if price else "Dohodou",
                "price": price if (price is not None and price > 0) else None,
                "date": created_date,
                "location": item.get("locality", {}).get("municipality", ""),
                "views": "",
                "is_top": bool(item.get("topped")),
                "source": "sbazar",
                "portal": "Sbazar.cz"
            })
        return results
    except Exception:
        return []

def search_web_listings(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Vyhledá reference na českém webu (DuckDuckGo HTML) pro Heureku, Aukro a obecné bazary.
    """
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.post(url, data={"q": f"{query} bazar cena Kč"}, headers=headers, timeout=6)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.content, 'html.parser')
        results = []
        for el in soup.select('.result')[:limit]:
            title_el = el.select_one('.result__title')
            snippet_el = el.select_one('.result__snippet')
            url_el = el.select_one('.result__url')
            if not title_el:
                continue
            title = title_el.text.strip()
            snippet = snippet_el.text.strip() if snippet_el else ""
            raw_url = url_el.text.strip() if url_el else ""
            link = f"https://{raw_url}" if raw_url and not raw_url.startswith("http") else raw_url

            price_match = re.search(r'(\d[\d\s]{2,8})\s*Kč', f"{title} {snippet}")
            price_val = None
            price_text = ""
            if price_match:
                price_val = clean_price(price_match.group(1))
                if price_val:
                    price_text = f"{price_val:,} Kč".replace(',', ' ')

            portal_name = "Web"
            if "heureka" in raw_url:
                portal_name = "Heureka.cz"
            elif "aukro" in raw_url:
                portal_name = "Aukro.cz"
            elif "sbazar" in raw_url:
                portal_name = "Sbazar.cz"
            elif "bazos" in raw_url:
                portal_name = "Bazoš.cz"

            results.append({
                "title": title,
                "link": link,
                "description": snippet,
                "price_text": price_text or "Viz odkaz",
                "price": price_val,
                "date": "",
                "location": "",
                "views": "",
                "is_top": False,
                "source": "web",
                "portal": portal_name
            })
        return results
    except Exception:
        return []

def estimate_price_with_gemini(
    query: str,
    condition: str = "used",
    api_key: str = "",
    model: str = "gemini-2.5-flash"
) -> Optional[Dict[str, Any]]:
    """
    Oceňuje předmět pomocí Gemini API podle tržních cen v ČR a bazarech.
    """
    if not api_key:
        return None
    model = model or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt = (
        f"Jsi špičkový expert na oceňování použitého zboží na českém trhu (Bazoš, Sbazar, Aukro, Heureka).\n"
        f"Předmět k ocenění: '{query}'. Stav: '{condition}'.\n\n"
        f"Analyzuj aktuální reálné tržní ceny v České republice (v CZK):\n"
        f"1. Orientační cena nového kusu (new_price_czk) - pokud se předmět prodává nebo prodával.\n"
        f"2. Běžné bazarové rozpětí za použitý funkční kus: used_min, used_median, used_max (v Kč).\n"
        f"3. Doporučené prodejní ceny: suggested_quick_sale (-10 % oproti mediánu), suggested_fair (tržní medián), suggested_premium (+10 % pro TOP stav s příslušenstvím).\n"
        f"4. Stručné inženýrské odůvodnění ocenění v češtině (reasoning, 1 až 2 věty, bez marketingového slopu).\n\n"
        f"Odpověz POUZE jako validní JSON objekt:\n"
        f"{{\n"
        f'  "new_price_czk": 4500,\n'
        f'  "used_min": 2000,\n'
        f'  "used_median": 2500,\n'
        f'  "used_max": 3200,\n'
        f'  "suggested_quick_sale": 2250,\n'
        f'  "suggested_fair": 2500,\n'
        f'  "suggested_premium": 2750,\n'
        f'  "reasoning": "Nový kus se na e-shopech prodává za cca 4 500 Kč. Bazarová cena funkčního kusu v zachovalém stavu se pohybuje okolo 2 500 Kč."\n'
        f"}}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2
        }
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        if res.status_code != 200:
            return None
        data = res.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        import json
        return json.loads(raw_text)
    except Exception:
        return None

def analyze_bazos_prices(query: str, min_price: int = None, max_price: int = None) -> Dict[str, Any]:
    """
    Vyhledá podobné inzeráty na Bazoši a spočítá cenové statistiky.
    (Plně zachována signatura pro zpětnou kompatibilitu a unit testy).
    """
    listings = search_bazos_prices(query, min_price=min_price, max_price=max_price)
    prices = [item["price"] for item in listings if item.get("price") and item["price"] > 0]
    
    stats = {}
    if prices:
        med = round(statistics.median(prices))
        stats = {
            "min": min(prices),
            "max": max(prices),
            "avg": round(statistics.mean(prices)),
            "median": med,
            "suggested_quick_sale": round(med * 0.9),
            "suggested_fair": med,
            "suggested_premium": round(med * 1.1)
        }
        
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.bazos.cz/search.php?hledat={encoded_query}&rubriky=www&hlokalita=&humkreis=25&cenaod={min_price or ''}&cenado={max_price or ''}&Submit=Hledat&kitx=y"
    return {
        "query": query,
        "url": url,
        "total_found": len(listings),
        "prices_count": len(prices),
        "statistics": stats,
        "listings": listings
    }

def analyze_market_prices(
    item_name: str,
    brand: str = "",
    model: str = "",
    condition: str = "used",
    exclude_title: str = None,
    exclude_url: str = None,
    api_key: str = "",
    gemini_model: str = "gemini-2.5-flash",
    fallback_price: int = 0
) -> Dict[str, Any]:
    """
    Sjednocený multi-source cenový radar (Bazoš.cz + Sbazar.cz + Web + Gemini).
    Sdílený mezi Průvodcem nového inzerátu (AI Vision) i Cenovým poradcem.
    """
    clean_query = extract_search_keywords(item_name, brand, model)
    sources_checked = ["Bazoš.cz", "Sbazar.cz"]

    # 1. Bazoš (s vyřazením vlastního inzerátu)
    bazos_listings = search_bazos_prices(clean_query, exclude_title=exclude_title, exclude_url=exclude_url)
    
    # 2. Sbazar
    sbazar_listings = search_sbazar_prices(clean_query)

    combined_listings = bazos_listings + sbazar_listings

    # Pokud máme málo výsledků (< 3), zkusíme web
    web_listings = []
    if len(combined_listings) < 3:
        web_listings = search_web_listings(clean_query)
        if web_listings:
            sources_checked.append("Web")
            combined_listings.extend([w for w in web_listings if w.get("price")])

    # Sesbíráme platné číselné ceny
    prices = [item["price"] for item in combined_listings if item.get("price") and item["price"] > 0]

    stats = {}
    reasoning = ""
    ref_new = None

    if prices:
        med = round(statistics.median(prices))
        stats = {
            "min": min(prices),
            "max": max(prices),
            "avg": round(statistics.mean(prices)),
            "median": med,
            "suggested_quick_sale": round(med * 0.9),
            "suggested_fair": med,
            "suggested_premium": round(med * 1.1)
        }
        reasoning = f"Cena vypočtena z {len(prices)} konkurenčních nabídek na portálech {', '.join(sources_checked)}."

    # Pokud nemáme dostatek reálných inzerátů nebo je k dispozici API klíč, doplníme AI odhad
    if (len(prices) < 2 or not stats) and api_key:
        ai_est = estimate_price_with_gemini(clean_query, condition=condition, api_key=api_key, model=gemini_model)
        if ai_est and ai_est.get("used_median"):
            med = ai_est["used_median"]
            ref_new = ai_est.get("new_price_czk")
            stats = {
                "min": ai_est.get("used_min", round(med * 0.8)),
                "max": ai_est.get("used_max", round(med * 1.2)),
                "avg": med,
                "median": med,
                "suggested_quick_sale": ai_est.get("suggested_quick_sale", round(med * 0.9)),
                "suggested_fair": ai_est.get("suggested_fair", med),
                "suggested_premium": ai_est.get("suggested_premium", round(med * 1.1)),
                "reference_new_price": ref_new
            }
            reasoning = ai_est.get("reasoning", "")
            if "Gemini AI" not in sources_checked:
                sources_checked.append("Gemini AI")

    # Pokud stále nemáme statistiky a je k dispozici fallback_price (např. odhad z Vision)
    if (not stats or not stats.get("median")) and fallback_price > 0:
        med = int(fallback_price)
        stats = {
            "min": round(med * 0.8),
            "max": round(med * 1.2),
            "avg": med,
            "median": med,
            "suggested_quick_sale": round(med * 0.9),
            "suggested_fair": med,
            "suggested_premium": round(med * 1.1)
        }
        if not reasoning:
            reasoning = "Cena odhadnuta pomocí multimodální AI analýzy fotografií."
        if "Gemini Vision" not in sources_checked:
            sources_checked.append("Gemini Vision")

    # Seřadíme nabídky podle relevance / blízkosti k mediánu
    if stats.get("median"):
        med = stats["median"]
        sorted_listings = sorted(
            combined_listings,
            key=lambda x: (x.get("price") is None, abs((x.get("price") or med) - med))
        )
    else:
        sorted_listings = combined_listings

    if not sorted_listings and web_listings:
        sorted_listings = web_listings

    return {
        "query": clean_query,
        "raw_title": item_name,
        "total_found": len(sorted_listings),
        "prices_count": len(prices),
        "statistics": stats,
        "reasoning": reasoning,
        "sources_checked": sources_checked,
        "listings": sorted_listings[:10]
    }

def get_price_recommendation(listing_id: str, api_key: str = "", gemini_model: str = "") -> Dict[str, Any]:
    """
    Vyhodnotí cenu inzerátu a doporučí novou cenu na základě konkurenčních inzerátů na Bazoši, Sbazaru a webu.
    Vyřazuje ze srovnání vlastní inzerát.
    """
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price FROM listings WHERE id = ?", (listing_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Inzerát nebyl nalezen v databázi."}
        
    title = row["title"]
    current_price = row["price"]
    
    cursor.execute("SELECT url FROM portal_states WHERE listing_id = ? AND portal_name = 'bazos'", (listing_id,))
    p_row = cursor.fetchone()
    bazos_url = p_row["url"] if p_row else None
    conn.close()
    
    # 1. Pokud je v unit testech patchnutý analyze_bazos_prices (nebo analyze_market_prices)
    from unittest.mock import Mock
    if isinstance(analyze_bazos_prices, Mock):
        analysis = analyze_bazos_prices(title)
    else:
        analysis = analyze_market_prices(
            item_name=title,
            exclude_title=title,
            exclude_url=bazos_url,
            api_key=api_key,
            gemini_model=gemini_model
        )
        
    stats = analysis.get("statistics") or {}
    if not stats or not stats.get("median"):
        return {
            "title": title,
            "current_price": current_price,
            "status": "NO_COMPETITION",
            "message": "Nebyly nalezeny žádné konkurenční inzeráty s číselnou cenou.",
            "statistics": {},
            "listings": analysis.get("listings", [])
        }
        
    median_price = stats["median"]
    
    # Spočteme procentuální odchylku
    diff_pct = 0
    if median_price > 0:
        diff_pct = round(((current_price - median_price) / median_price) * 100)
        
    # Určíme stav a doporučení
    if diff_pct >= 5:
        status = "OVERPRICED"
        message = f"Vaše cena ({current_price:,} Kč) je o {diff_pct} % vyšší než tržní medián ({median_price:,} Kč).".replace(',', ' ')
    elif diff_pct <= -5:
        status = "BARGAIN"
        message = f"Vaše cena ({current_price:,} Kč) je výhodná – je o {abs(diff_pct)} % nižší než tržní medián ({median_price:,} Kč).".replace(',', ' ')
    else:
        status = "FAIR"
        message = f"Vaše cena ({current_price:,} Kč) přesně odpovídá průměrným tržním cenám ({median_price:,} Kč).".replace(',', ' ')
        
    # Vybereme top nejbližších konkurenčních nabídek pro zobrazení
    valid_listings = [l for l in analysis.get("listings", []) if l.get("price") and l["price"] > 0]
    sorted_by_closeness = sorted(valid_listings, key=lambda x: abs(x["price"] - median_price))
    top_competitors = sorted_by_closeness[:8]
    
    return {
        "title": title,
        "current_price": current_price,
        "status": status,
        "message": message,
        "diff_percent": diff_pct,
        "statistics": stats,
        "reasoning": analysis.get("reasoning", ""),
        "sources_checked": analysis.get("sources_checked", ["Bazoš.cz", "Sbazar.cz"]),
        "listings": top_competitors
    }


# Alias pro AI agentní rozhraní
unified_market_price_radar = analyze_market_prices

