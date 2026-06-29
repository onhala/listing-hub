#!/usr/bin/env python3
import sys
import requests
from bs4 import BeautifulSoup
import re
import statistics
import urllib.parse

def clean_price(price_str):
    """
    Cleans a price string and returns an integer value.
    Returns None if price is not numeric (e.g. 'Dohodou', 'V textu', etc.)
    """
    price_str = price_str.replace('\xa0', '').replace(' ', '')
    match = re.search(r'(\d+)', price_str)
    if match:
        return int(match.group(1))
    return None

def analyze_bazos(query, min_price=None, max_price=None):
    """
    Searches Bazos.cz and calculates price statistics for similar listings.
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
        # Title & Link
        title_el = el.find(class_='nadpis')
        if not title_el or not title_el.find('a'):
            continue
        title = title_el.find('a').text.strip()
        link = title_el.find('a')['href']
        if link.startswith('/'):
            link = f"https://www.bazos.cz{link}"
            
        # Description
        desc_el = el.find(class_='popis')
        description = desc_el.text.strip() if desc_el else ""
        
        # Price
        price_el = el.find(class_='inzeratycena')
        price_text = price_el.text.strip() if price_el else ""
        price_val = clean_price(price_text)
        
        # Date
        date_el = el.find(class_='velikost10')
        date_str = ""
        if date_el:
            # Extract date like [29.6. 2026]
            date_match = re.search(r'\[(.*?)\]', date_el.text)
            if date_match:
                date_str = date_match.group(1)
                
        # Location
        lok_el = el.find(class_='inzeratylok')
        location = lok_el.text.strip().replace('\r', ' ').replace('\n', ' ') if lok_el else ""
        location = re.sub(r'\s+', ' ', location)
        
        # Views
        view_el = el.find(class_='inzeratyview')
        views = view_el.text.strip() if view_el else ""
        
        # Is TOP
        is_top = False
        if el.find(class_='ztop'):
            is_top = True
            
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

def print_text_report(data):
    if "error" in data:
        print(f"❌ Chyba: {data['error']}")
        return
        
    print(f"🔍 Výsledky analýzy pro dotaz: \"{data['query']}\"")
    print(f"🌐 Zdroj: {data['url']}")
    print(f"📊 Celkem nalezeno inzerátů: {data['total_found']}")
    print(f"💰 S platnou cenou: {data['prices_count']}")
    print("-" * 60)
    
    if data['prices_count'] == 0:
        print("⚠️ Nebyly nalezeny žádné inzeráty s číselnou cenou pro výpočet statistik.")
        return
        
    stats = data['statistics']
    print("📈 Cenové rozpětí:")
    print(f"  • Minimální cena:  {stats['min']:,} Kč".replace(',', ' '))
    print(f"  • Průměrná cena:   {stats['avg']:,} Kč".replace(',', ' '))
    print(f"  • Mediánová cena:  {stats['median']:,} Kč".replace(',', ' '))
    print(f"  • Maximální cena:  {stats['max']:,} Kč".replace(',', ' '))
    print("-" * 60)
    
    print("💡 Doporučení ceny pro tvůj inzerát:")
    print(f"  • Rychlý prodej (-10% z mediánu):      {stats['suggested_quick_sale']:,} Kč".replace(',', ' '))
    print(f"  • Férová tržní cena (medián):          {stats['suggested_fair']:,} Kč".replace(',', ' '))
    print(f"  • Prémiová cena (TOP/záruka/stav +10%): {stats['suggested_premium']:,} Kč".replace(',', ' '))
    print("-" * 60)
    
    print("🎯 Top 5 konkurenčních nabídek:")
    # Sort listings by price (excluding None and 0)
    valid_listings = [l for l in data['listings'] if l['price'] is not None and l['price'] > 0]
    # Sort by views (higher is more interesting) or just price
    # Let's show top 5 closest to median
    median_val = stats['median']
    sorted_by_closeness = sorted(valid_listings, key=lambda x: abs(x['price'] - median_val))
    
    for i, item in enumerate(sorted_by_closeness[:5]):
        top_str = " [TOP]" if item['is_top'] else ""
        print(f"  {i+1}. {item['title']} - {item['price_text']}{top_str}")
        print(f"     📍 {item['location']} | 📅 {item['date']} | 👁️ {item['views']}")
        print(f"     🔗 {item['link']}")
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Použití: python3 bazos_analyzer.py \"hledaný výraz\" [min_cena] [max_cena]")
        sys.exit(1)
        
    search_query = sys.argv[1]
    min_c = int(sys.argv[2]) if len(sys.argv) > 2 else None
    max_c = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    res = analyze_bazos(search_query, min_c, max_c)
    print_text_report(res)
