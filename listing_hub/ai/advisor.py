import statistics
import urllib.parse
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import requests
from listing_hub.core import db

def clean_price(price_str: str) -> int:
    """Očistí textovou cenu na integer."""
    if not price_str:
        return None
    price_str = price_str.replace('\xa0', '').replace(' ', '')
    match = re.search(r'(\d+)', price_str)
    if match:
        return int(match.group(1))
    return None

def analyze_bazos_prices(query: str, min_price: int = None, max_price: int = None) -> Dict[str, Any]:
    """
    Vyhledá podobné inzeráty na Bazoši a spočítá cenové statistiky.
    """
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.bazos.cz/search.php?hledat={encoded_query}&rubriky=www&hlokalita=&humkreis=25&cenaod={min_price or ''}&cenado={max_price or ''}&Submit=Hledat&kitx=y"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"error": f"Nepodařilo se připojit k Bazošu (HTTP {response.status_code})"}
    except Exception as e:
        return {"error": f"Chyba při stahování: {str(e)}"}
        
    soup = BeautifulSoup(response.content, 'html.parser')
    listings = soup.find_all(class_='inzeraty')
    
    results = []
    prices = []
    
    for el in listings:
        title_el = el.find(class_='nadpis')
        if not title_el or not title_el.find('a'):
            continue
        title = title_el.find('a').text.strip()
        link = title_el.find('a')['href']
        if link.startswith('/'):
            link = f"https://www.bazos.cz{link}"
            
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
        
        is_top = True if el.find(class_='ztop') else False
            
        item = {
            "title": title,
            "link": link,
            "description": description,
            "price_text": price_text,
            "price": price_val,
            "date": date_str,
            "location": location,
            "views": views,
            "is_top": is_top
        }
        
        results.append(item)
        if price_val is not None and price_val > 0:
            prices.append(price_val)
            
    if not results:
        return {
            "query": query,
            "url": url,
            "total_found": 0,
            "prices_count": 0,
            "listings": []
        }
        
    stats = {}
    if prices:
        stats = {
            "min": min(prices),
            "max": max(prices),
            "avg": round(statistics.mean(prices)),
            "median": round(statistics.median(prices)),
            "suggested_quick_sale": round(statistics.median(prices) * 0.9),
            "suggested_fair": round(statistics.median(prices)),
            "suggested_premium": round(statistics.median(prices) * 1.1)
        }
        
    return {
        "query": query,
        "url": url,
        "total_found": len(results),
        "prices_count": len(prices),
        "statistics": stats,
        "listings": results
    }

def get_price_recommendation(listing_id: str) -> Dict[str, Any]:
    """
    Vyhodnotí cenu inzerátu a doporučí zlevnění na základě konkurenčních inzerátů na Bazoši.
    """
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, price FROM listings WHERE id = ?", (listing_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"error": "Inzerát nebyl nalezen v databázi."}
        
    title = row["title"]
    current_price = row["price"]
    
    # Spustíme analýzu cen na Bazoši
    analysis = analyze_bazos_prices(title)
    if "error" in analysis:
        return analysis
        
    if analysis["prices_count"] == 0:
        return {
            "title": title,
            "current_price": current_price,
            "status": "NO_COMPETITION",
            "message": "Nebyly nalezeny žádné konkurenční inzeráty s číselnou cenou.",
            "statistics": {},
            "listings": []
        }
        
    stats = analysis["statistics"]
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
        message = f"Vaše cena ({current_price:,} Kč) přesně odpovídá průměrným tržním cenám."
        
    # Vybereme top 5 konkurenčních nabídek pro zobrazení
    valid_listings = [l for l in analysis["listings"] if l["price"] is not None and l["price"] > 0]
    sorted_by_closeness = sorted(valid_listings, key=lambda x: abs(x["price"] - median_price))
    top_competitors = sorted_by_closeness[:5]
    
    return {
        "title": title,
        "current_price": current_price,
        "status": status,
        "message": message,
        "diff_percent": diff_pct,
        "statistics": stats,
        "listings": top_competitors
    }
