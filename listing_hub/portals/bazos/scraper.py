import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from listing_hub.portals.bazos.date_parser import parse_bazos_date

def scrape_listings_from_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Vyparsuje inzeráty ze stránky Moje inzeráty na Bazoši.
    """
    if not html_content:
        return []
        
    soup = BeautifulSoup(html_content, "html.parser")
    ad_elements = soup.find_all(class_=re.compile(r"\binzeraty\b"))
    
    scraped_listings = []
    
    for el in ad_elements:
        try:
            nadpis_el = el.find(class_="nadpis")
            if not nadpis_el:
                continue
            a_tag = nadpis_el.find("a")
            if not a_tag:
                continue
                
            title_text = a_tag.get_text().strip()
            ad_url = a_tag.get("href", "")
            
            if ad_url.startswith("/"):
                ad_url = "https://www.bazos.cz" + ad_url
            elif not ad_url.startswith("http"):
                ad_url = "https://" + ad_url
                
            cena_el = el.find(class_="inzeratycena")
            price_val = 0
            if cena_el:
                cena_text = cena_el.get_text().replace(" ", "").replace("\xa0", "")
                price_match = re.search(r"(\d+)", cena_text)
                if price_match:
                    price_val = int(price_match.group(1))
                    
            views_el = el.find(class_="inzeratyview")
            views_val = 0
            if views_el:
                views_text = views_el.get_text().replace(" ", "").replace("\xa0", "")
                views_match = re.search(r"(\d+)", views_text)
                if views_match:
                    views_val = int(views_match.group(1))
                    
            date_el = el.find(class_="velikost10")
            date_str = ""
            if date_el:
                date_text = date_el.get_text().strip()
                date_str = parse_bazos_date(date_text)
                
            scraped_listings.append({
                "title": title_text,
                "url": ad_url,
                "price": price_val,
                "views": views_val,
                "date_created": date_str
            })
        except Exception:
            continue
            
    return scraped_listings
